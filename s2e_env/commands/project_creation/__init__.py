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
import logging
import os
import shutil
import stat
import time

from jinja2 import Environment, FileSystemLoader

from s2e_env.command import EnvCommand, CommandError
from s2e_env.commands.image_build import get_image_templates, ImageDownloaderMixin
from s2e_env import CONSTANTS


logger = logging.getLogger('new_project')

FILE_DIR = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(FILE_DIR, '..', '..', 'templates')


def datetimefilter(value, format_='%H:%M %d-%m-%Y'):
    """
    Jinja2 filter.
    """
    return value.strftime(format_)


class BaseProject(EnvCommand, ImageDownloaderMixin):
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

    def _validate_binary(self, target_arch, os_name, os_arch, os_binary_formats):
        if target_arch == 'x86_64' and os_arch != 'x86_64':
            raise CommandError('Binary is x86_64 while VM image is %s. Please '
                               'choose another image.' % os_arch)

    def _guess_image(self, target_arch):
        """
        At this stage, images may not exist, so we get the list of images
        from images.json rather than from the images folder.
        """
        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])
        templates = get_image_templates(img_build_dir)

        logger.info('No image was specified (-i option). Attempting to guess '
                    'a suitable image for a %s binary', target_arch)

        for k, v in templates.iteritems():
            try:
                self._validate_binary(target_arch, v['os_name'], v['os_arch'], v['os_binary_formats'])
                logger.warning('Found %s, which looks suitable for this '
                               'binary. Please use -i if you want to use '
                               'another image', k)
                return k
            except Exception:
                pass

        raise CommandError('No suitable image available for this binary')

    def _get_or_download_image(self, image, download):
        try:
            return self._load_image_json(image)
        except Exception:
            if not download:
                raise

        logger.info('Image %s missing, attempting to download...', image)
        self.download_images(image)
        return self._load_image_json(image)

    def handle(self, *args, **options):
        self._target_path = options['target']

        # The default project name is the target program to be analyzed
        # (without any file extension)
        project_name = options['name']
        if not project_name:
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
        image = options['image']
        if image is None:
            image = self._guess_image(options['target_arch'])

        self._img_json = self._get_or_download_image(image,
                                                     options['download_image'])

        # Check architecture consistency
        self._validate_binary(
            options['target_arch'], self._img_json['os_name'],
            self._img_json['os_arch'], self._img_json['os_binary_formats']
        )

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
        logger.info('Creating launch script')
        self._create_launch_script()

        logger.info('Creating bootstrap script')
        self._create_bootstrap()

        logger.info('Creating S2E config')
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
        img_json_path = self.image_path(img_name, 'image.json')

        try:
            with open(img_json_path, 'r') as f:
                ret = json.load(f)
                ret['path'] = self.image_path(img_name, 'image.raw.s2e')
                return ret
        except Exception:
            raise CommandError('Unable to open image description %s\n'
                               'Check that the image exists, was built, or '
                               'downloaded' % img_json_path)

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
                logger.info('\'%s\' already exists - removing',
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
        logger.info('Creating JSON description')

        project_desc_path = os.path.join(self._project_path, 'project.json')

        creation_time = time.mktime(datetime.datetime.now().timetuple())
        project_desc = {
            'target': self._target_path,
            'creation_time': creation_time,
            'arch': self._arch,
            'image': self._img_json
        }

        with open(project_desc_path, 'w') as f:
            json.dump(project_desc, f)

    @property
    def _arch(self):
        """
        The architecture is determined by the QEMU executable used to build the
        image.
        """
        return self._img_json['qemu_build']

    def _symlink_target(self):
        """
        Create a symlink to the target program.
        """
        logger.info('Creating a symlink to %s', self._target_path)

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

        logger.info('Creating a symlink to %s', guest_tools_path)

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

    def _create_launch_script(self):
        """
        Create the S2E launch script.
        """
        # Render the launch scripts
        for template in CONSTANTS['templates']['launch_scripts']:
            context = {
                'current_time': datetime.datetime.now(),
                'env_dir': self.env_path(),
                'install_dir': self.install_path(),
                'build_dir': self.build_path(),
                'arch': self._arch,
                'image_path': self._img_json['path'],
                'memory': self._img_json['memory'],
                'snapshot': self._img_json['snapshot'],
                'qemu_extra_flags': self._img_json['qemu_extra_flags'],
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
