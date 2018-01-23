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
from s2e_env.commands.image_build import get_image_templates, get_image_descriptor
from s2e_env.utils.image_download import ImageDownloader
from s2e_env.utils.templates import render_template
from .config import is_valid_arch


logger = logging.getLogger('new_project')


def _create_instructions(context):
    ret = render_template(context, 'instructions.txt')
    # Due to how templates work, there may be many useless new lines, remove
    # them here
    return re.sub(r'([\r\n][\r\n])+', r'\n\n', ret)


class Project(EnvCommand):
    """
    Helper class used by the ``new_project`` command to create a specific
    project.
    """
    def __init__(self, cfg):
        super(Project, self).__init__()

        self._configurator = cfg()
        self._target_path = None
        self._project_dir = None
        self._img_json = None

    def handle(self, *args, **options):
        self._validate_and_create_project(options)

        # Prepare the configuration for file templates
        config = {
            'creation_time': str(datetime.datetime.now()),
            'project_dir': self._project_dir,
            'project_type': self._configurator.PROJECT_TYPE,
            'image': self._img_json,
            'target': os.path.basename(self._target_path),
            'target_path': self._target_path,
            'target_arch': options['target_arch'],
            'target_args': options['target_args'],

            # These contain all the files that must be downloaded into the guest
            'target_files': [],

            # List of module names that go into ModuleExecutionDetector
            'modules': options['modules'],

            # List of binaries that go into ProcessExecutionDetector
            # These are normally executable files
            'processes': options['processes'],

            'sym_args': options['sym_args'],

            # See _create_bootstrap for an explanation of the @@ marker
            'use_symb_input_file': '@@' in options['target_args'],

            # The use of seeds is specified on the command line
            'use_seeds': options['use_seeds'],
            'seeds_dir': os.path.join(self._project_dir, 'seeds'),

            # The use of recipes is set by the configurator
            'use_recipes': False,
            'recipes_dir': os.path.join(self._project_dir, 'recipes'),

            # The use of guestfs is dependent on the specific image
            'has_guestfs': True,
            'guestfs_dir': os.path.join(self._project_dir, 'guestfs'),

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
            'use_fault_injection': False
        }

        for tf in options['target_files']:
            if not os.path.exists(tf):
                raise CommandError('%s does not exist' % tf)

            config['target_files'].append(os.path.basename(tf))

        # The configurator may modify the config dictionary here
        self._configurator.validate_configuration(config)

        if config['warn_input_file'] and not (config['use_symb_input_file'] or config['sym_args']):
            logger.warning('You did not specify the input file marker @@. This marker is automatically substituted by '
                           'a file with symbolic content. You will have to manually edit the bootstrap file in order '
                           'to run the program on multiple paths.\n\n'
                           'Example: %s @@\n\n'
                           'You can also make arguments symbolic using the ``S2E_SYM_ARGS`` environment variable in '
                           'the bootstrap file', self._target_path)

        if config['use_seeds'] and not config['use_symb_input_file'] and config['warn_seeds']:
            logger.warning('Seed files have been enabled, however you did not '
                           'specify an input file marker (i.e. \'@@\') to be '
                           'substituted with a seed file. This means that '
                           'seed files will be fetched but never used. Is '
                           'this intentional?')

        if config['use_seeds'] and not os.path.isdir(config['seeds_dir']):
            os.mkdir(config['seeds_dir'])

        if config['use_recipes']:
            recipes_path = self.install_path('share', 'decree-recipes')
            os.symlink(recipes_path, config['recipes_dir'])

        # Do some basic analysis on the target
        self._configurator.analyze(config)

        # Create a symlink to the guest tools directory
        self._symlink_guest_tools()

        # Create a symlink to the target program
        self._symlink_target_files(options['target_files'])

        # Create a symlink to guestfs (if it exists)
        if not self._symlink_guestfs():
            config['has_guestfs'] = False

        # Render the templates
        logger.info('Creating launch script')
        self._create_launch_script(config)

        logger.info('Creating S2E configuration')
        self._create_lua_config(config)

        logger.info('Creating S2E bootstrap script')
        self._create_bootstrap(config)

        # Record some basic information on the project
        self._save_json_description(config)

        # Return the instructions to the user
        logger.success(_create_instructions(config))

    def _create_launch_script(self, config):
        """
        Create the S2E launch script.
        """
        template = 'launch-s2e.sh'
        script_path = os.path.join(self._project_dir, template)
        context = {
            'creation_time': config['creation_time'],
            'env_dir': self.env_path(),
            'rel_image_path': os.path.relpath(config['image']['path'], self.env_path()),
            'qemu_arch': self._qemu_arch,
            'qemu_memory': config['image']['memory'],
            'qemu_snapshot': config['image']['snapshot'],
            'qemu_extra_flags': config['image']['qemu_extra_flags'],
        }

        render_template(context, template, script_path, executable=True)

    def _create_lua_config(self, config):
        """
        Create the S2E Lua config.
        """
        context = {
            'creation_time': config['creation_time'],
            'target': config['target'],
            'target_lua_template': self._configurator.LUA_TEMPLATE,
            'project_dir': config['project_dir'],
            'use_seeds': config['use_seeds'],
            'use_cupa': config['use_cupa'],
            'use_test_case_generator': config['use_test_case_generator'],
            'seeds_dir': config['seeds_dir'],
            'has_guestfs': config['has_guestfs'],
            'guestfs_dir': config['guestfs_dir'],
            'recipes_dir': config['recipes_dir'],
            'target_files': config['target_files'],
            'modules': config['modules'],
            'processes': config['processes'],
        }

        for f in ('s2e-config.lua', 'models.lua', 'library.lua'):
            output_path = os.path.join(self._project_dir, f)
            render_template(context, f, output_path)

    def _create_bootstrap(self, config):
        """
        Create the S2E bootstrap script.
        """
        # The target arguments are specified using a format similar to the
        # American Fuzzy Lop fuzzer. Options are specified as normal, however
        # for programs that take input from a file, '@@' is used to mark the
        # location in the target's command line where the input file should be
        # placed. This will automatically be substituted with a symbolic file
        # in the S2E bootstrap script.
        parsed_args = ['${SYMB_FILE}' if arg == '@@' else arg
                       for arg in config['target_args']]

        template = 'bootstrap.sh'
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
            'dynamically_linked': config['dynamically_linked'],
            'project_type': config['project_type'],
            'target_files': config['target_files'],
            'modules': config['modules'],
            'processes': config['processes'],
        }

        script_path = os.path.join(self._project_dir, template)
        render_template(context, template, script_path)

    def _validate_and_create_project(self, options):
        self._target_path = options['target']

        # Check that the analysis target is valid
        if not os.path.isfile(self._target_path):
            raise CommandError('Cannot analyze %s because it does not seem to '
                               'exist' % self._target_path)

        # The default project name is the target program to be analyzed
        # (without any file extension)
        project_name = options['name']
        if not project_name:
            project_name, _ = \
                os.path.splitext(os.path.basename(self._target_path))

        self._project_dir = self.env_path('projects', project_name)

        # Load the image JSON description. If it is not given, guess the image
        image = options['image']
        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])
        templates = get_image_templates(img_build_dir)

        if not image:
            image = self._guess_image(templates, options['target_arch'])

        self._img_json = self._get_or_download_image(templates, image, options['download_image'])

        # Check architecture consistency
        if not is_valid_arch(options['target_arch'], self._img_json['os']):
            raise CommandError('Binary is x86_64 while VM image is %s. Please '
                               'choose another image' % self._img_json['os']['arch'])

        # Check if the project dir already exists
        # Do this after all checks have completed
        self._check_project_dir(options['force'])

        # Create the project directory
        os.mkdir(self._project_dir)

    def _guess_image(self, templates, target_arch):
        """
        At this stage, images may not exist, so we get the list of images
        from images.json (in the guest-images repo) rather than from the images
        folder.
        """
        logger.info('No image was specified (-i option). Attempting to guess '
                    'a suitable image for a %s binary', target_arch)

        for k, v in templates.iteritems():
            if self._configurator.is_valid_binary(target_arch, self._target_path, v['os']):
                logger.warning('Found %s, which looks suitable for this '
                               'binary. Please use -i if you want to use '
                               'another image', k)
                return k

        raise CommandError('No suitable image available for this binary')

    def _get_or_download_image(self, templates, image, do_download=True):
        img_json_path = self.image_path(image)

        try:
            return get_image_descriptor(img_json_path)
        except CommandError:
            if not do_download:
                raise

        logger.info('Image %s missing, attempting to download...', image)
        image_downloader = ImageDownloader(templates)
        image_downloader.download_images([image], self.image_path())

        return get_image_descriptor(img_json_path)

    def _check_project_dir(self, force=False):
        """
        Check if a project dir with the given name already exists.

        If such a project exists, only continue if the ``force`` flag has been
        specified.
        """
        if not os.path.isdir(self._project_dir):
            return

        if force:
            logger.info('\'%s\' already exists - removing',
                        os.path.basename(self._project_dir))
            shutil.rmtree(self._project_dir)
        else:
            raise CommandError('\'%s\' already exists. Either remove this '
                               'project or use the force option' %
                               os.path.basename(self._project_dir))

    def _save_json_description(self, config):
        """
        Create a JSON description of the project.

        This information can be used by other commands.
        """
        logger.info('Creating JSON description')
        project_desc_path = os.path.join(self._project_dir, 'project.json')
        with open(project_desc_path, 'w') as f:
            s = json.dumps(config, sort_keys=True, indent=4)
            f.write(s)

    @property
    def _qemu_arch(self):
        """
        The architecture is determined by the QEMU executable used to build the
        image.
        """
        return self._img_json['qemu_build']

    def _symlink_target_files(self, files):
        """
        Create a symlinks to the files that compose the program.
        """
        for f in files:
            logger.info('Creating a symlink to %s', self._target_path)
            target_file = os.path.basename(f)
            os.symlink(f, os.path.join(self._project_dir, target_file))

    def _symlink_guest_tools(self):
        """
        Create a symlink to the guest tools directory.
        """
        guest_tools_path = \
            self.install_path('bin', CONSTANTS['guest_tools'][self._qemu_arch])

        logger.info('Creating a symlink to %s', guest_tools_path)
        os.symlink(guest_tools_path,
                   os.path.join(self._project_dir, 'guest-tools'))

    def _symlink_guestfs(self):
        """
        Create a symlink to the guestfs directory.

        Return ``True`` if the guestfs directory exists, or ``False``
        otherwise.
        """
        image_name = os.path.dirname(self._img_json['path'])
        guestfs_path = self.image_path(image_name, 'guestfs')

        if not os.path.exists(guestfs_path):
            logger.warn('%s does not exist, the VMI plugin may not run optimally',
                        guestfs_path)
            return False

        logger.info('Creating a symlink to %s', guestfs_path)
        os.symlink(guestfs_path,
                   os.path.join(self._project_dir, 'guestfs'))

        return True
