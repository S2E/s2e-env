"""
Copyright (c) 2017 Cyberhaven
Copyright (c) 2017 Dependable Systems Laboratory, EPFL

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


import datetime
import json
import logging
import os
import re
import shutil

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError
from s2e_env.commands.recipe import Command as RecipeCommand
from s2e_env.manage import call_command
from s2e_env.utils.images import ImageDownloader, get_image_templates, get_image_descriptor
from s2e_env.utils.templates import render_template
from .config import is_valid_arch


logger = logging.getLogger('new_project')


def _check_project_dir(project_dir, force=False):
    """
    Check if a project directory with the given name already exists.

    If such a project exists, only continue if the ``force`` flag has been
    specified.
    """
    if not os.path.isdir(project_dir):
        return

    if force:
        logger.info('\'%s\' already exists - removing',
                    os.path.basename(project_dir))
        shutil.rmtree(project_dir)
    else:
        raise CommandError('\'%s\' already exists. Either remove this '
                           'project or use the force option' %
                           os.path.basename(project_dir))


class Project(EnvCommand):
    """
    Helper class used by the ``new_project`` command to create a specific
    project.
    """

    def __init__(self, cfg):
        super(Project, self).__init__()

        self._configurator = cfg

    def handle(self, *args, **options):
        # Check that the target files are valid
        target_files = options['target_files']
        if target_files:
            for tf in target_files:
                if not os.path.isfile(tf):
                    raise CommandError('Target file %s is not valid' % tf)
        else:
            logger.warn('Creating a project without a target file. You must '
                        'manually edit bootstrap.sh')

        # The target program that will be executed is the first target file
        if target_files:
            target_path = target_files[0]
        else:
            target_path = None

        target_arch = options['target_arch']

        # Decide on the image to be used
        img_desc = self._select_image(target_path, target_arch, options)

        # Check architecture consistency (if the target has been specified)
        if target_path and not is_valid_arch(target_arch, img_desc['os']):
            raise CommandError('Binary is %s while VM image is %s. Please '
                               'choose another image' % (target_arch,
                                                         img_desc['os']['arch']))

        # Determine if guestfs is available for this image
        guestfs_path = self._select_guestfs(img_desc)
        if not guestfs_path:
            logger.warn('No guestfs available. The VMI plugin may not run optimally')

        # Create an empty project directory
        project_dir = self._create_project_dir(target_path, options)

        # Prepare the project configuration
        config = {
            'creation_time': str(datetime.datetime.now()),
            'project_dir': project_dir,
            'project_type': self._configurator.PROJECT_TYPE,
            'image': img_desc,
            'target': os.path.basename(target_path) if target_path else None,
            'target_arch': target_arch,
            'target_args': options['target_args'],

            # This contains all the files that must be downloaded into the guest
            'target_files': [os.path.basename(tf) for tf in target_files],

            # List of module names that go into ModuleExecutionDetector
            'modules': options['modules'],

            # List of binaries that go into ProcessExecutionDetector
            # These are normally executable files
            'processes': options['processes'],

            # Target arguments to be made symbolic
            'sym_args': options['sym_args'],

            # See _create_bootstrap for an explanation of the @@ marker
            'use_symb_input_file': '@@' in options['target_args'],

            # The use of seeds is specified on the command line
            'use_seeds': options['use_seeds'],
            'seeds_dir': os.path.join(project_dir, 'seeds'),

            # The use of recipes is set by the configurator
            'use_recipes': False,
            'recipes_dir': os.path.join(project_dir, 'recipes'),

            # The use of guestfs is dependent on the specific image
            'has_guestfs': guestfs_path is not None,
            'guestfs_path': guestfs_path,

            # These options are determined by the configurator's analysis
            'dynamically_linked': False,
            'modelled_functions': False,

            # Configurators can silence warnings in case they have specific
            # hard-coded options
            'warn_seeds': True,
            'warn_input_file': True,

            # Searcher options
            'use_cupa': True,

            'use_test_case_generator': True,
            'use_fault_injection': False,

            # This will add analysis overhead, so disable unless requested by
            # the user. Also enabled by default for Decree targets.
            'enable_pov_generation': options['enable_pov_generation']
        }

        # Do some basic analysis on the target (if it exists)
        if target_path:
            self._configurator.analyze(target_path, config)

        if config['use_seeds'] and not os.path.isdir(config['seeds_dir']):
            os.mkdir(config['seeds_dir'])

        if config['enable_pov_generation']:
            config['use_recipes'] = True

        # The configurator may modify the config dictionary here. After this
        # point the config should NOT be modified
        self._configurator.validate_configuration(config)

        # Create symlinks to the target files (if they exist)
        if target_files:
            self._symlink_target_files(project_dir, target_files)

        # Create a symlink to the guest tools directory
        self._symlink_guest_tools(project_dir, config)

        # Create a symlink to guestfs (if it exists)
        if guestfs_path:
            self._symlink_guestfs(project_dir, config)

        # Render the templates
        self._create_launch_script(project_dir, config)
        self._create_lua_config(project_dir, config)
        self._create_bootstrap(project_dir, config)

        # Record some basic information on the project
        self._save_json_description(project_dir, config)

        # Generate recipes for PoV generation
        if config['use_recipes']:
            os.makedirs(config['recipes_dir'])
            call_command(RecipeCommand(), env=options['env'],
                         project=os.path.basename(project_dir))

        # Display messages/instructions to the user
        display_marker_warning = target_path and \
                                 config['warn_input_file'] and \
                                 not (config['use_symb_input_file'] or config['sym_args'])

        if display_marker_warning:
            logger.warning('You did not specify the input file marker @@. '
                           'This marker is automatically substituted by a '
                           'file with symbolic content. You will have to '
                           'manually edit the bootstrap file in order to run '
                           'the program on multiple paths.\n\n'
                           'Example: %s @@\n\n'
                           'You can also make arguments symbolic using the '
                           '``S2E_SYM_ARGS`` environment variable in the '
                           'bootstrap file', target_path)

        if config['use_seeds'] and not config['use_symb_input_file'] and config['warn_seeds']:
            logger.warning('Seed files have been enabled, however you did not '
                           'specify an input file marker (i.e. \'@@\') to be '
                           'substituted with a seed file. This means that '
                           'seed files will be fetched but never used. Is '
                           'this intentional?')

        logger.success(self._create_instructions(config))

    def _create_launch_script(self, project_dir, config):
        """
        Create the S2E launch script.
        """
        logger.info('Creating launch script')

        context = {
            'creation_time': config['creation_time'],
            'env_dir': self.env_path(),
            'rel_image_path': os.path.relpath(config['image']['path'], self.env_path()),
            'qemu_arch': config['image']['qemu_build'],
            'qemu_memory': config['image']['memory'],
            'qemu_snapshot': config['image']['snapshot'],
            'qemu_extra_flags': config['image']['qemu_extra_flags'],
        }

        template = 'launch-s2e.sh'
        script_path = os.path.join(project_dir, template)
        render_template(context, template, script_path, executable=True)

    def _create_lua_config(self, project_dir, config):
        """
        Create the S2E Lua config.
        """
        logger.info('Creating S2E configuration')

        context = {
            'creation_time': config['creation_time'],
            'target': config['target'],
            'target_lua_template': self._configurator.LUA_TEMPLATE,
            'project_dir': config['project_dir'],
            'use_seeds': config['use_seeds'],
            'use_cupa': config['use_cupa'],
            'use_test_case_generator': config['use_test_case_generator'],
            'enable_pov_generation': config['enable_pov_generation'],
            'seeds_dir': config['seeds_dir'],
            'has_guestfs': config['has_guestfs'],
            'guestfs_path': config['guestfs_path'],
            'recipes_dir': config['recipes_dir'],
            'target_files': config['target_files'],
            'modules': config['modules'],
            'processes': config['processes'],
        }

        for f in ('s2e-config.lua', 'models.lua', 'library.lua'):
            output_path = os.path.join(project_dir, f)
            render_template(context, f, output_path)

    def _create_bootstrap(self, project_dir, config):
        """
        Create the S2E bootstrap script.
        """
        logger.info('Creating S2E bootstrap script')

        # The target arguments are specified using a format similar to the
        # American Fuzzy Lop fuzzer. Options are specified as normal, however
        # for programs that take input from a file, '@@' is used to mark the
        # location in the target's command line where the input file should be
        # placed. This will automatically be substituted with a symbolic file
        # in the S2E bootstrap script.
        parsed_args = ['${SYMB_FILE}' if arg == '@@' else arg
                       for arg in config['target_args']]

        context = {
            'creation_time': config['creation_time'],
            'target': config['target'],
            'target_args': parsed_args,
            'sym_args': config['sym_args'],
            'target_bootstrap_template': self._configurator.BOOTSTRAP_TEMPLATE,
            'image_arch': config['image']['os']['arch'],
            'use_symb_input_file': config['use_symb_input_file'],
            'use_seeds': config['use_seeds'],
            'use_fault_injection': config['use_fault_injection'],
            'enable_pov_generation': config['enable_pov_generation'],
            'dynamically_linked': config['dynamically_linked'],
            'project_type': config['project_type'],
            'target_files': config['target_files'],
            'modules': config['modules'],
            'processes': config['processes'],
        }

        template = 'bootstrap.sh'
        script_path = os.path.join(project_dir, template)
        render_template(context, template, script_path)

    def _create_project_dir(self, target_path, options):
        project_name = options['name']
        if not project_name:
            # The default project name is the target program without any file
            # extension
            project_name, _ = os.path.splitext(os.path.basename(target_path))

        project_dir = self.env_path('projects', project_name)

        # Check if the project directory already exists
        _check_project_dir(project_dir, options['force'])

        # Create the project directory
        os.mkdir(project_dir)

        return project_dir

    def _select_image(self, target_path, target_arch, options):
        """
        Select the image to use for this project.

        If an image was specified, use it. Otherwise select an image to use
        based on the target's architecture. If the image is not available, it
        may be downloaded.

        Returns:
            A dictionary that describes the image that will be used, based on
            the image's JSON descriptor.
        """
        # Load the image JSON description. If it is not given, guess the image
        image = options['image']
        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])
        img_templates = get_image_templates(img_build_dir)

        if not image:
            image = self._guess_image(target_path, img_templates, target_arch)

        return self._get_or_download_image(img_templates, image, options['download_image'])

    def _guess_image(self, target_path, templates, target_arch):
        """
        At this stage, images may not exist, so we get the list of images
        from images.json (in the guest-images repo) rather than from the images
        folder.
        """
        logger.info('No image was specified (-i option). Attempting to guess '
                    'a suitable image for a %s binary...', target_arch)

        for k, v in templates.iteritems():
            if self._configurator.is_valid_binary(target_arch, target_path, v['os']):
                logger.warning('Found %s, which looks suitable for this '
                               'binary. Please use -i if you want to use '
                               'another image', k)
                return k

        raise CommandError('No suitable image available for this binary')

    def _get_or_download_image(self, templates, image, do_download=True):
        img_path = self.image_path(image)

        try:
            return get_image_descriptor(img_path)
        except CommandError:
            if not do_download:
                raise

        logger.info('Image %s missing, attempting to download...', image)
        image_downloader = ImageDownloader(templates)
        image_downloader.download_images([image], self.image_path())

        return get_image_descriptor(img_path)

    def _select_guestfs(self, img_desc):
        image_dir = os.path.dirname(img_desc['path'])
        guestfs_path = self.image_path(image_dir, 'guestfs')

        return guestfs_path if os.path.exists(guestfs_path) else None

    def _save_json_description(self, project_dir, config):
        """
        Create a JSON description of the project.

        This information can be used by other commands.
        """
        logger.info('Creating JSON description')

        project_desc_path = os.path.join(project_dir, 'project.json')
        with open(project_desc_path, 'w') as f:
            s = json.dumps(config, sort_keys=True, indent=4)
            f.write(s)

    def _symlink_target_files(self, project_dir, files):
        """
        Create symlinks to the files that compose the program.
        """
        for f in files:
            logger.info('Creating a symlink to %s', f)
            target_file = os.path.basename(f)
            os.symlink(f, os.path.join(project_dir, target_file))

    def _symlink_guest_tools(self, project_dir, config):
        """
        Create a symlink to the guest tools directory.
        """
        img_arch = config['image']['qemu_build']
        guest_tools_path = \
            self.install_path('bin', CONSTANTS['guest_tools'][img_arch])

        logger.info('Creating a symlink to %s', guest_tools_path)
        os.symlink(guest_tools_path,
                   os.path.join(project_dir, 'guest-tools'))

    def _symlink_guestfs(self, project_dir, config):
        """
        Create a symlink to the guestfs directory.

        Return ``True`` if the guestfs directory exists, or ``False``
        otherwise.
        """
        guestfs_path = config['guestfs_path']
        logger.info('Creating a symlink to %s', guestfs_path)
        os.symlink(guestfs_path,
                   os.path.join(project_dir, 'guestfs'))

        return True

    def _create_instructions(self, config):
        instructions = render_template(config, 'instructions.txt')

        # Due to how templates work, there may be many useless new lines, remove
        # them here
        return re.sub(r'([\r\n][\r\n])+', r'\n\n', instructions)
