"""
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
import os
import shutil
import stat
import time

from jinja2 import Environment, FileSystemLoader

from s2e_env.command import EnvCommand, CommandError
from s2e_env import CONSTANTS

FILE_DIR = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(FILE_DIR, '..', '..', 'templates')


def datetimefilter(value, format_='%H:%M %d-%m-%Y'):
    """
    Jinja2 filter.
    """
    return value.strftime(format_)


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
        guest_tools_path = self.install_path(
            'bin', CONSTANTS['guest_tools'][self._arch]
        )

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
                'install_dir': self.install_path(),
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
