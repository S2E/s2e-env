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
import logging
import os
import re
import shutil

from s2e_env.command import CommandError
from s2e_env.commands.recipe import Command as RecipeCommand
from s2e_env.manage import call_command
from s2e_env.utils.templates import render_template
from .abstract_project import AbstractProject


logger = logging.getLogger('new_project')


def _check_project_dir(project_dir, force=False):
    """
    Check if a project directory with the given name already exists.

    If such a project exists, only continue if the ``force`` flag has been
    specified.
    """

    if os.path.exists(project_dir) and not os.path.isdir(project_dir):
        raise CommandError(f'The path {project_dir} already exists and is a file.')

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


def is_valid_arch(target_arch, os_desc):
    """
    Check that the image's architecture is consistent with the target binary.
    """
    return not (target_arch == 'x86_64' and os_desc['arch'] != 'x86_64')


class BaseProject(AbstractProject):
    """
    Base class used by the ``new_project`` command to create a specific
    project. The ``make_project`` method builds up a configuration dictionary
    that is then used to generate the required files for the project. CGC,
    Linux and Windows projects extend this class. These projects implement
    methods to validate the configuration dictionary and do basic static
    analysis on the target.
    """

    def __init__(self, bootstrap_template, lua_template):
        super(BaseProject, self).__init__()

        self._bootstrap_template = bootstrap_template
        self._lua_template = lua_template

    def _configure(self, target, *args, **options):
        if target.is_empty():
            logger.warning('Creating a project without a target file. You must manually edit bootstrap.sh')

        # Decide on the image to be used
        img_desc = self._select_image(target, options.get('image'),
                                      options.get('download_image', False))

        # Check architecture consistency (if the target has been specified)
        if target.path and not is_valid_arch(target.arch, img_desc['os']):
            raise CommandError('Binary is %s while VM image is %s. Please '
                               'choose another image' % (target.arch,
                                                         img_desc['os']['arch']))

        # Determine if guestfs is available for this image
        guestfs_paths = self._select_guestfs(img_desc)
        if not guestfs_paths:
            logger.warning('No guestfs available. The VMI plugin may not run optimally')

        target.translated_path = self._translate_target_path_to_guestfs(target.path, guestfs_paths)

        # Generate the name of the project directory. The default project name
        # is the target program name without any file extension
        project_name = options.get('name')
        if project_name:
            dir_name, name = os.path.split(project_name)
            if not name:
                raise CommandError(f'{project_name} is invalid.')
            project_name = name
            project_dir = self.env_path('projects', dir_name, project_name)
        else:
            project_name, _ = os.path.splitext(target.name)
            project_dir = self.env_path('projects', project_name)

        # Prepare the project configuration
        config = {
            'creation_time': str(datetime.datetime.now()),
            'project_dir': project_dir,
            'project_name': project_name,
            'image': img_desc,
            'target': target,

            # List of module names that go into ModuleExecutionDetector
            'modules': [(target.name, False)] if target.name else [],

            # List of binaries that go into ProcessExecutionDetector. These are
            # normally executable files
            'processes': [target.name] if target.name else [],

            # Target arguments to be made symbolic
            'sym_args': options.get('sym_args', []),

            # The use of seeds is specified on the command line
            'use_seeds': options.get('use_seeds', False),
            'seeds_dir': os.path.join(project_dir, 'seeds'),

            # The use of recipes is set by the specific project
            'use_recipes': False,
            'recipes_dir': os.path.join(project_dir, 'recipes'),

            # The use of guestfs is dependent on the specific image
            'has_guestfs': guestfs_paths is not None,
            'guestfs_paths': guestfs_paths,

            # These options are determined by a static analysis of the target
            'dynamically_linked': False,
            'modelled_functions': False,

            # Specific projects can silence warnings in case they have specific
            # hard-coded options
            'warn_seeds': True,
            'warn_input_file': True,

            # Searcher options
            'use_cupa': True,

            'use_test_case_generator': True,
            'use_fault_injection': False,

            # This will add analysis overhead, so disable unless requested by
            # the user. Also enabled by default for Decree targets.
            'enable_pov_generation': options.get('enable_pov_generation', False),

            'single_path': options.get('single_path', False)
        }

        # Do some basic analysis on the target (if it exists)
        if target.path:
            self._analyze_target(target, config)

        if config['enable_pov_generation']:
            config['use_recipes'] = True

        # After this point the config dictionary should NOT be modified
        self._finalize_config(config)

        return config

    def _create(self, config, force=False):
        project_dir = config['project_dir']
        target = config['target']

        # Check if the project directory already exists
        _check_project_dir(project_dir, force)

        # Create the project directory
        os.makedirs(project_dir)

        if config['use_seeds'] and not os.path.isdir(config['seeds_dir']):
            os.mkdir(config['seeds_dir'])

        # Create symlinks to the target files (if they exist)
        if target.files:
            self._symlink_project_files(project_dir, *target.files)

        target.args.generate_symbolic_files(project_dir, config['use_seeds'])

        # Create symlinks to symbolic files
        if target.args.symbolic_files:
            self._symlink_project_files(project_dir, *target.args.symbolic_files)

        # Create a symlink to the guest tools directory
        self._symlink_guest_tools(project_dir, config['image'])

        # Create a symlink to guestfs (if it exists)
        if config['guestfs_paths']:
            self._symlink_guestfs(project_dir, config['guestfs_paths'])

        # Render the templates
        self._create_launch_script(project_dir, config)
        self._create_lua_config(project_dir, config)
        self._create_bootstrap(project_dir, config)

        # Even though the AbstractProject will save the project description, we
        # need it to be able to generate recipes below
        self._save_json_description(project_dir, config)

        # Generate recipes for PoV generation
        if config['use_recipes']:
            os.makedirs(config['recipes_dir'])
            call_command(RecipeCommand(), [], project=project_dir)

        # Display relevant messages to the user
        display_marker_warning = config['target'].path and \
                                 config['warn_input_file'] and \
                                 not config['single_path'] and \
                                 not (config['target'].args.symbolic_files or config['sym_args'])

        if display_marker_warning:
            logger.warning('You did not specify any symbolic input. '
                           'Symbolic execution requires symbolic inputs. You will have to '
                           'manually edit the bootstrap file in order to run '
                           'the program on multiple paths.\n\n'
                           'Example: %s @@\n\n'
                           'You can also make arguments symbolic using the '
                           '``S2E_SYM_ARGS`` environment variable in the '
                           'bootstrap file', config['target'].path)

        seed_files_count = len(config['target'].args.blank_seed_files)
        if config['use_seeds'] and config['warn_seeds']:
            if not seed_files_count:
                logger.warning('Seed files have been enabled, however you did not '
                               'specify an input file marker (i.e. \'@@\') to be '
                               'substituted with a seed file. This means that '
                               'seed files will be fetched but never used. Is '
                               'this intentional?')
            if seed_files_count > 1:
                raise CommandError('You specified multiple symbolic inputs with @@. You may only have one '
                                   'when seeds are enabled.')

        return project_dir

    def _get_instructions(self, config):
        instructions = render_template(config, 'instructions.txt')

        # Due to how templates work, there may be many useless new lines,
        # remove them here
        return re.sub(r'([\r\n][\r\n])+', r'\n\n', instructions)

    def _finalize_config(self, config):
        """
        Validate and finalize a project's configuration options.

        This method may modify values in the ``config`` dictionary. If an
        invalid configuration is found, a ``CommandError` should be thrown.
        """

    def _analyze_target(self, target, config):
        """
        Perform static analysis on the target binary.

        The results of this analysis can be used to add and/or modify values in
        the ``config`` dictionary.
        """

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
            'single_path': config['single_path'],
        }

        template = 'launch-s2e.sh'
        output_path = os.path.join(project_dir, template)
        render_template(context, template, output_path, executable=True)

    def _create_lua_config(self, project_dir, config):
        """
        Create the S2E Lua config.
        """
        logger.info('Creating S2E configuration')

        self._copy_lua_library(project_dir)

        context = {
            'creation_time': config['creation_time'],
            'target': config['target'],
            'target_lua_template': self._lua_template,
            'project_dir': project_dir,
            'project_name': config['project_name'],
            'use_seeds': config['use_seeds'],
            'use_cupa': config['use_cupa'],
            'use_test_case_generator': config['use_test_case_generator'],
            'enable_pov_generation': config['enable_pov_generation'],
            'seeds_dir': config['seeds_dir'],
            'single_path': config['single_path'],
            'has_guestfs': config['has_guestfs'],
            'guestfs_paths': config['guestfs_paths'],
            'recipes_dir': config['recipes_dir'],
            'modules': config['modules'],
            'processes': config['processes'],
        }

        for template in ('s2e-config.lua', 'models.lua'):
            output_path = os.path.join(project_dir, template)
            render_template(context, template, output_path)

    def _create_bootstrap(self, project_dir, config):
        """
        Create the S2E bootstrap script.
        """
        logger.info('Creating S2E bootstrap script')

        context = {
            'project_name': config['project_name'],
            'creation_time': config['creation_time'],
            'target': config['target'],
            'sym_args': config['sym_args'],
            'target_bootstrap_template': self._bootstrap_template,
            'image_arch': config['image']['os']['arch'],
            'use_seeds': config['use_seeds'],
            'use_fault_injection': config['use_fault_injection'],
            'enable_pov_generation': config['enable_pov_generation'],
            'single_path': config['single_path'],
            'dynamically_linked': config['dynamically_linked'],
            'project_type': config['project_type'],
            'modules': config['modules'],
            'processes': config['processes'],
        }

        template = 'bootstrap.sh'
        output_path = os.path.join(project_dir, template)
        render_template(context, template, output_path)
