"""
MIT License

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


import argparse
import datetime
import json
import os
import re
import shutil
import stat
import time

from jinja2 import Environment, FileSystemLoader

from magic import Magic

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError
from s2e_env.manage import call_command
from s2e_env.utils.elf import ELFAnalysis


# Paths
FILE_DIR = os.path.dirname(__file__)
CGC_MAGIC = os.path.join(FILE_DIR, '..', 'dat', 'cgc.magic')
TEMPLATES_DIR = os.path.join(FILE_DIR, '..', 'templates')

# Magic regexs
CGC_REGEX = re.compile(r'^CGC 32-bit')
ELF32_REGEX = re.compile(r'^ELF 32-bit')
ELF64_REGEX = re.compile(r'^ELF 64-bit')
PE32_REGEX = re.compile(r'^PE executable')
PE64_REGEX = re.compile(r'^PE\+ executable')


def datetimefilter(value, format_='%H:%M %d-%m-%Y'):
    """
    Jinja2 filter.
    """
    return value.strftime(format_)

#
# Project creation classes
#

class BaseProject(EnvCommand):
    """
    The base class for the different projects that the ``new_project`` command
    can create.
    """

    # Footer for the user instructions
    INST_HEADER =                                                           \
        'Project \'{project_name}\' created.'
    INST_FOOTER =                                                           \
        'Running S2E\n===========\n\nPlease check s2e-config.lua, '         \
        'bootstrap.sh and launch-s2e.sh in {project_dir} and modify them '  \
        'as necessary.\n\n'                                                 \
        'Once you have done so, you are ready to run S2E. To start the '    \
        'analysis ``cd {project_dir}`` and run ``./launch-s2e.sh``. The '   \
        'results of the analysis can be found in the ``s2e-last`` directory.'

    def __init__(self):
        super(BaseProject, self).__init__()

        self._target_path = None
        self._project_path = None
        self._img_json = None
        self._use_seeds = None

        # Initialize the jinja2 template environment
        self._template_env = \
            Environment(loader=FileSystemLoader(TEMPLATES_DIR),
                        autoescape=False)
        self._template_env.filters['datetimefilter'] = datetimefilter

    def handle(self, **options):
        self._target_path = options['target']

        # The default project name is the target program to be analyzed
        # (without any file extension)
        project_name = options['name']
        if not project_name:
            if not self._target_path:
                raise CommandError('If you are creating an empty project you '
                                   'must specify a project name using the '
                                   '``--name`` option')
            project_name, _ = \
                os.path.splitext(os.path.basename(self._target_path))

        # Save the project directory. Check if the project directory makes
        # sense
        if not os.path.isdir(self.env_path('projects')):
            raise CommandError('A ``projects`` directory does not exist in '
                               'your S2E environment. Are you sure this is an '
                               'S2E environment?')
        self._project_path = self.env_path('projects', project_name)

        # Load the image JSON description
        self._img_json = self._load_image_json(options['image'])

        # Save use seeds flag
        self._use_seeds = options['use_seeds']

        # Check that the analysis target is valid
        if self._target_path and not os.path.isfile(self._target_path):
            raise CommandError('Cannot analyze %s because it does not seem to '
                               'seem to exist' % self._target_path)

        # Check if the project dir already exists
        self._check_project_dir(options['force'])

        # Create the project directory
        os.mkdir(self._project_path)

        # Do some basic analysis on the target
        self._analyze()

        # Render the templates
        self.info('Creating launch scripts')
        self._create_launch_scripts()

        self.info('Creating bootstrap script')
        self._create_bootstrap()

        self.info('Creating S2E config')
        self._create_config()

        # Create misc. directories required by the project
        self._create_dirs()

        # Create a symlink to the guest tools directory
        self._symlink_guest_tools()

        # Create a symlink to the target program
        self._symlink_target()

        # Create a seeds directory if required
        seeds_path = os.path.join(self._project_path, 'seeds')
        if self._use_seeds and not os.path.isdir(seeds_path):
            os.mkdir(seeds_path)

        # Record some basic information on the project
        self._save_json_description()

        # Return the instructions to the user
        inst_header = self.INST_HEADER.format(project_name=project_name)
        inst_footer = self.INST_FOOTER.format(project_dir=self._project_path)
        return '\n\n'.join([inst_header,
                            self._create_instructions(),
                            inst_footer])

    def _load_image_json(self, img_name):
        """
        Load the image JSON description.

        Args:
            img_name: The name of an image JSON description file (with or
                      without the .json extension).
        """
        # Construct the path to the image description file
        img_json_path = self.env_path('images', '.%s' % img_name)

        if not img_json_path.endswith('.json'):
            img_json_path = '%s.json' % img_json_path

        # Try to load the image description file
        try:
            with open(img_json_path, 'r') as f:
                return json.load(f)
        except Exception:
            raise CommandError('Unable to open image description %s' %
                               os.path.basename(img_json_path))

    def _create_empty(self):
        """
        Create an empty project.

        The project will be created in the S2E environment's ``projects``
        directory. The created project differs to that created by the
        ``_create`` method in that it consists only of the launch scripts.
        """
        # Check if the project dir already exists
        self._check_project_dir()

        # Create the project directory
        os.mkdir(self._project_path)

        # Render the templates
        self.info('Creating launch scripts')
        self._create_launch_scripts()

        # Return the instructions to the user
        return ('Empty project \'%s\' created' %
                os.path.basename(self._project_path))

    def _check_project_dir(self, force=False):
        """
        Check if a project dir with the given name already exists.

        If such a project exists, only continue if the ``force`` flag has been
        specifed.
        """
        # Check if a project dir with this name already exists. If it does,
        # only continue if the ``force`` flag has been specified
        if os.path.isdir(self._project_path):
            if force:
                self.info('\'%s\' already exists - removing' %
                          os.path.basename(self._project_path))
                shutil.rmtree(self._project_path)
            else:
                raise CommandError('\'%s\' already exists. Either remove this '
                                   'project or use the force option' %
                                   os.path.basename(self._project_path))

    def _save_json_description(self):
        """
        Create a JSON description of the project.

        This information can be used by other commands.
        """
        self.info('Creating JSON description')

        project_desc_path = os.path.join(self._project_path, '.project.json')

        creation_time = time.mktime(datetime.datetime.now().timetuple())
        project_desc = {
            'target': self._target_path,
            'creation_time': creation_time,
        }

        with open(project_desc_path, 'w') as f:
            json.dump(project_desc, f)

    @property
    def _arch(self):
        """
        The architecture is determined by the QEMU executable used to build the
        image.
        """
        return self._img_json['qemu'].split('-')[-1]

    def _symlink_target(self):
        """
        Create a symlink to the target program.
        """
        self.info('Creating a symlink to %s' % self._target_path)

        target_file = os.path.basename(self._target_path)
        os.symlink(self._target_path,
                   os.path.join(self._project_path, target_file))

    def _symlink_guest_tools(self):
        """
        Create a symlink to the guest tools directory.
        """
        guest_tools_path = self.env_path('bin',
                                        CONSTANTS['guest_tools'][self._arch])

        self.info('Creating a symlink to %s' % guest_tools_path)

        os.symlink(guest_tools_path,
                   os.path.join(self._project_path, 'guest-tools'))

    def _render_template(self, context, template, path, executable=False):
        """
        Renders the ``template`` template with the given ``context``. The
        result is written to ``path``.
        """
        with open(path, 'w') as f:
            data = self._template_env.get_template(template).render(context)
            f.write(data)
            if executable:
                st = os.stat(path)
                os.chmod(path, st.st_mode | stat.S_IEXEC)

    def _create_launch_scripts(self):
        """
        Create the S2E launch scripts.
        """
        # Render the launch scripts
        for template in CONSTANTS['templates']['launch_scripts']:
            context = {
                'current_time': datetime.datetime.now(),
                'env_dir': self.env_path(),
                'arch': self._arch,
                'image_path': self._img_json['path'],
                'memory': self._img_json['memory'],
                'snapshot': self._img_json['snapshot'],
            }

            script_path = os.path.join(self._project_path, template)
            self._render_template(context, template, script_path,
                                  executable=True)

    def _analyze(self):
        """
        Do some simple analysis on the target program.

        Overriding this function is optional.
        """
        pass

    def _create_bootstrap(self):
        """
        Create a bootstrap script.
        """
        raise NotImplementedError('Subclasses of BaseProject must provide a '
                                  '_create_bootstrap() method')

    def _create_config(self):
        """
        Create an S2E config file.
        """
        raise NotImplementedError('Subclasses of BaseProject must provide a '
                                  '_create_config() method')

    def _create_dirs(self):
        """
        Create any additional directories in the project dir.

        Overriding this function is optional.
        """
        pass

    def _create_instructions(self):
        """
        Create instructions for the user on how to run their project.

        Returns:
            A string containing the instructions.
        """
        raise NotImplementedError('Subclasses of BaseProject must provide a '
                                  '_create_instructions() method')


class CGCProject(BaseProject):
    """
    Create a CGC project.
    """

    # User instruction templates
    SEEDS_INSTS =                                                           \
        'Seed Files\n'                                                      \
        '==========\n\n'                                                    \
        'Seed files have been enabled. This means that seed files will be ' \
        'used to drive concolic execution. Please place seeds in '          \
        '{seeds_dir}. Seed files must be named using the following '        \
        'format:\n\n'                                                       \
        '\t``<index>-<priority>.pov``\n\n'                                  \
        'Where:\n'                                                          \
        '\t* <index> is a unique integer identifier starting from 0\n'      \
        '\t* <priority> is an integer priority, where 0 is the highest '    \
        'priorty\n'                                                         \
        'Examples:\n'                                                       \
        '\t0-1.pov, 1-1.pov, 2-0.pov, etc.\n\n'                             \
        'Seeds can be based on real files, generated by a fuzzer, or '      \
        'randomly.'

    def handle(self, **options):
        options['use_seeds'] = True

        return super(CGCProject, self).handle(**options)

    def _create_bootstrap(self):
        # Render the bootstrap script
        context = {
            'current_time': datetime.datetime.now(),
            'target': os.path.basename(self._target_path),
            'use_seeds': self._use_seeds,
        }

        output_path = os.path.join(self._project_path, 'bootstrap.sh')
        self._render_template(context, 'bootstrap.cgc.sh', output_path,
                              executable=True)

    def _create_config(self):
        # Render the config file
        context = {
            'current_time': datetime.datetime.now(),
            'project_dir': self._project_path,
            'target': os.path.basename(self._target_path),
            'use_seeds': self._use_seeds,
        }

        output_path = os.path.join(self._project_path, 's2e-config.lua')
        self._render_template(context, 's2e-config.cgc.lua', output_path)

    def _create_dirs(self):
        recipes_path = self.env_path('share', 'decree-recipes')
        seeds_path = os.path.join(self._project_path, 'seeds')

        # Create a symlink to the recipes directory
        self.info('Creating a symlink to %s' % recipes_path)

        os.symlink(recipes_path, os.path.join(self._project_path, 'recipes'))

        # Since the Recipe plugin relies on SeedSearcher, we always need a
        # seeds directory
        os.mkdir(seeds_path)

    def _create_instructions(self):
        intro = 'Here are some hints to get started with your CGC project:'

        seeds = ''
        if self._use_seeds:
            seeds_dir = os.path.join(self._project_path, 'seeds')
            seeds = self.SEEDS_INSTS.format(seeds_dir=seeds_dir)

        # Remove empty instructions
        inst_list = [intro, seeds]
        return '\n\n'.join(inst for inst in inst_list if inst != '')


class LinuxProject(BaseProject):
    """
    Create a Linux project.
    """

    # User instruction templates
    S2E_SO_INSTS =                                                          \
        's2e.so\n'                                                          \
        '======\n\n'                                                        \
        '{target_path} is dynamically linked - you can use s2e.so to '      \
        'generate symbolic input'

    FUNC_MODELS_INSTS =                                                     \
        'Function Models\n'                                                 \
        '===============\n\n'                                               \
        '{target_path} is dynamically linked and imports the following '    \
        'functions that can be modelled using S2E\'s ``FunctionModels`` '   \
        'plugin:\n\n'                                                       \
        '\t{modelled_funcs}\n\n'                                            \
        'The ``FunctionModels`` plugin can be enabled in s2e-config.lua.'

    SEEDS_INSTS =                                                           \
        'Seed Files\n'                                                      \
        '==========\n\n'                                                    \
        'You have enabled seed files. This means that seed files will be '  \
        'used to drive concolic execution. Please place seeds in '          \
        '{seeds_dir}. Seed files must be named using the following '        \
        'format:\n\n'                                                       \
        '\t``<index>-<priority>.<extension>``\n\n'                          \
        'Where:\n'                                                          \
        '\t* <index> is a unique integer identifier starting from 0\n'      \
        '\t* <priority> is an integer priority, where 0 is the highest '    \
        'priorty\n'                                                         \
        '\t* <extension> an optional file extension\n'                      \
        'Examples:\n'                                                       \
        '\t0-1.png, 1-1.jpg, 2-0.elf, etc.\n\n'                             \
        'Seeds can be based on real files (e.g. a PNG image if testing a '  \
        'PNG parser), generated by a fuzzer, or randomly.'

    def __init__(self):
        super(LinuxProject, self).__init__()

        self._target_args = None
        self._dynamically_linked = False
        self._modelled_functions = []

    def handle(self, **options):
        self._target_args = options['target_args']

        return super(LinuxProject, self).handle(**options)

    def _parse_target_args(self):
        """
        Parse the target program's arguments.

        The target arguments are specified using a format similar to the
        American Fuzzy Lop fuzzer. Options are specified as normal, however
        for programs that take input from a file, '@@' is used to mark the
        location in the target's command line where the input file should be
        placed. This will automatically be substituted with a symbolic file
        in the S2E bootstrap script.

        Return:
            A tuple containing:
                1. A flag that is ``True`` if a '@@' marker was found and
                   replaced with a symbolic file, or ``False`` if no such
                   marker was found
                2. A list of the new command-line arguments to render to
                   bootstrap.sh
        """
        use_symb_input_file = False
        parsed_args = []

        if self._use_seeds:
            input_file_substitution = '${SEED_FILE}'
        else:
            input_file_substitution = '${SYMB_FILE}'

        for arg in self._target_args:
            if arg == '@@':
                use_symb_input_file = True
                parsed_args.append(input_file_substitution)
            else:
                parsed_args.append(arg)

        if self._use_seeds and not use_symb_input_file:
            self.warn('Seed files have been enabled, however you did not  '
                      'specify an input file marker (i.e. \'@@\') to be '
                      'substituted with a seed file. This means that seed '
                      'files will be fetched but never used. Is this '
                      'intentional?')

        return use_symb_input_file, parsed_args

    def _analyze(self):
        with ELFAnalysis(self._target_path) as elf:
            self._dynamically_linked = elf.is_dynamically_linked()
            self._modelled_functions = elf.get_modelled_functions()

    def _create_bootstrap(self):
        # Parse the target's command-line arguments
        use_symb_input_file, parsed_args = self._parse_target_args()

        # Render the bootstrap script
        context = {
            'current_time': datetime.datetime.now(),
            'target': os.path.basename(self._target_path),
            'target_args': parsed_args,
            'use_symb_input_file': use_symb_input_file,
            'dynamically_linked': self._dynamically_linked,
            'use_seeds': self._use_seeds,
        }

        output_path = os.path.join(self._project_path, 'bootstrap.sh')
        self._render_template(context, 'bootstrap.linux.sh', output_path,
                              executable=True)

    def _create_config(self):
        # Render the config file
        context = {
            'current_time': datetime.datetime.now(),
            'project_dir': self._project_path,
            'target': os.path.basename(self._target_path),
            'function_models': len(self._modelled_functions) > 0,
            'use_seeds': self._use_seeds,
        }

        output_path = os.path.join(self._project_path, 's2e-config.lua')
        self._render_template(context, 's2e-config.linux.lua', output_path)

    def _create_instructions(self):
        intro = 'Here are some hints to get started with your Linux project:'

        s2e_so = ''
        func_models = ''
        if self._dynamically_linked:
            s2e_so = self.S2E_SO_INSTS.format(target_path=self._target_path)

            if len(self._modelled_functions) > 0:
                modelled_funcs = ', '.join(self._modelled_functions)
                func_models = self.FUNC_MODELS_INSTS.format(\
                                                target_path=self._target_path,
                                                modelled_funcs=modelled_funcs)

        seeds = ''
        if self._use_seeds:
            seeds_dir = os.path.join(self._project_path, 'seeds')
            seeds = self.SEEDS_INSTS.format(seeds_dir=seeds_dir)

        # Remove empty instructions
        inst_list = [intro, s2e_so, func_models, seeds]
        return '\n\n'.join(inst for inst in inst_list if inst != '')


class WindowsProject(BaseProject):
    """
    Create a Windows project.
    """

    def handle(self, **options):
        raise CommandError('Windows project support not yet implemented')

    def _create_bootstrap(self):
        pass

    def _create_config(self):
        pass

    def _create_instructions(self):
        pass


#
# The actual command class to execute from the command line
#

class Command(EnvCommand):
    """
    Initialize a new analysis project.
    """

    help = 'Initialize a new analysis project.'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('target', nargs='?',
                            help='Path to the target file to analyze. You may '
                                 'leave this empty, in which case an empty '
                                 'Linux project will be created')
        parser.add_argument('target_args', nargs=argparse.REMAINDER,
                            help='Arguments to the target program')
        parser.add_argument('-n', '--name', required=False, default=None,
                            help='The name of the project. Defaults to the '
                                 'name of the target program. If you are '
                                 'creating an empty project then this field '
                                 'must be specified')
        parser.add_argument('-i', '--image', required=True,
                            help='The name of an image in the ``images`` '
                                 'directory (without a file extension)')
        parser.add_argument('-s', '--use-seeds', action='store_true',
                            help='Use this option to use seeds for creating '
                                 'concolic files. The user must create these '
                                 'seeds themselves and place them in the '
                                 'project\'s ``seeds`` directory')
        parser.add_argument('-f', '--force', action='store_true',
                            help='If a project with the given name already '
                                 'exists, replace it')

    def handle(self, **options):
        target_path = options['target']
        magic_checks = [
            (Magic(magic_file=CGC_MAGIC), CGC_REGEX, CGCProject),
            (Magic(), ELF32_REGEX, LinuxProject),
            (Magic(), ELF64_REGEX, LinuxProject),
            (Magic(), PE32_REGEX, WindowsProject),
            (Magic(), PE64_REGEX, WindowsProject),
        ]

        # Check the target program against the valid file types
        for magic_check, regex, proj_class in magic_checks:
            magic = magic_check.from_file(target_path)
            matches = regex.match(magic)

            # If we find a match, create that project. The user instructions
            # are returned
            if matches:
                return call_command(proj_class(), **options)

        # Otherwise no valid file type was found
        raise CommandError('%s is not a valid target for S2E analysis' %
                           target_path)
