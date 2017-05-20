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
from s2e_env.commands.image_build import \
      get_image_templates, get_image_descriptor, ImageDownloaderMixin

from s2e_env.utils.templates import render_template


logger = logging.getLogger('new_project')


def _parse_target_args(target_args):
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
               bootstrap.{bat, sh}
    """
    use_symb_input_file = False
    parsed_args = []

    for arg in target_args:
        if arg == '@@':
            use_symb_input_file = True
            parsed_args.append('${SYMB_FILE}')
        else:
            parsed_args.append(arg)

    return use_symb_input_file, parsed_args


class BaseProject(EnvCommand, ImageDownloaderMixin):
    """
    The base class for the different projects that the ``new_project`` command
    can create.
    """
    def __init__(self, cfg):
        super(BaseProject, self).__init__()

        self._configurator = cfg()
        self._target_path = None
        self._project_dir = None
        self._img_json = None

    def handle(self, *args, **options):
        self._validate_and_create_project(options)

        use_symb_input_file, parsed_args = _parse_target_args(
            options['target_args']
        )

        # Prepare context for configuration file templates
        context = {
            'creation_time': str(datetime.datetime.now()),
            'project_dir': self._project_dir,
            'project_type': self._configurator.PROJECT_TYPE,
            'target': os.path.basename(self._target_path),
            'target_path': self._target_path,
            'target_arch': options['target_arch'],
            'target_args': parsed_args,
            'image': self._img_json,
            'use_seeds': options['use_seeds'],
            'seeds_dir': os.path.join(self._project_dir, 'seeds'),
            'use_recipes': False,
            'recipes_dir': os.path.join(self._project_dir, 'recipes'),
            'guestfs_dir': os.path.join(self._project_dir, 'guestfs'),
            'use_symb_input_file': use_symb_input_file,
            'dynamically_linked': False,
            'modelled_functions': False,

            # Configurators can silence warnings in case they have
            # specific hard-coded options
            'warn_seeds': True,
            'warn_input_file': True,
        }

        self._configurator.validate_configuration(context)

        use_symb_input_file = context.get('use_symb_input_file', False)

        if context['warn_input_file'] and not use_symb_input_file:
            logger.warning('You did not specify the input file marker @@. '
                           'This marker is automatically substituted by a '
                           'file with symbolic content. You will have to '
                           'manually edit the bootstrap file in order to run the '
                           'program on multiple paths.\n\n'
                           'Example: %s @@', self._target_path)

        use_seeds = context.get('use_seeds', False)

        if use_seeds and not use_symb_input_file and context['warn_seeds']:
            logger.warning('Seed files have been enabled, however you did not '
                           'specify an input file marker (i.e. \'@@\') to be '
                           'substituted with a seed file. This means that '
                           'seed files will be fetched but never used. Is '
                           'this intentional?')

        if use_seeds and not os.path.isdir(context['seeds_dir']):
            os.mkdir(context['seeds_dir'])

        if context['use_recipes']:
            recipes_path = self.install_path('share', 'decree-recipes')
            os.symlink(recipes_path, context['recipes_dir'])

        # Do some basic analysis on the target
        self._configurator.analyze(context)

        # Create a symlink to the guest tools directory
        self._symlink_guest_tools()

        # Create a symlink to the target program
        self._symlink_target()

        # Create a symlink to guestfs
        if not self._symlink_guestfs(os.path.dirname(self._img_json['path'])):
            context['guestfs_dir'] = None

        # Render the templates
        logger.info('Creating launch script')
        self._create_launch_script()

        logger.info('Creating S2E configuration and bootstrap')
        self._create_config(context)

        # Record some basic information on the project
        self._save_json_description(context)

        # Return the instructions to the user
        return self._create_instructions(context)

    def _create_instructions(self, context):
        ret = render_template(context, 'instructions.txt')
        # Due to how templates work, there may be many useless new lines,
        # remove them here.
        return re.sub(r'([\r\n][\r\n])+', r'\n\n', ret)

    def _create_config(self, context):
        context['target_bootstrap_template'] = self._configurator.BOOTSTRAP_TEMPLATE
        context['target_lua_template'] = self._configurator.LUA_TEMPLATE

        for f in ('s2e-config.lua', 'models.lua', 'library.lua', 'bootstrap.sh'):
            output_path = os.path.join(self._project_dir, f)
            render_template(context, f, output_path)

    def _create_launch_script(self):
        """
        Create the S2E launch script.
        """
        template = 'launch-s2e.sh'
        script_path = os.path.join(self._project_dir, template)
        context = {
            'env_dir': self.env_path(),
            'install_dir': self.install_path(),
            'build_dir': self.build_path(),
            'arch': self._arch,
            'image_path': self._img_json['path'],
            'memory': self._img_json['memory'],
            'snapshot': self._img_json['snapshot'],
            'qemu_extra_flags': self._img_json['qemu_extra_flags'],
        }

        render_template(context, template, script_path, executable=True)

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

        # Load the image JSON description
        image = options['image']
        if not image:
            image = self._guess_image(options['target_arch'])

        self._img_json = self._get_or_download_image(image, options['download_image'])

        # Check architecture consistency
        ios = self._img_json['os']
        self._configurator.validate_binary(options['target_arch'], ios)

        # Check if the project dir already exists
        # Do this after all checks have completed
        self._check_project_dir(options['force'])

        # Create the project directory
        os.mkdir(self._project_dir)

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
                self._configurator.validate_binary(target_arch, v['os'])
                logger.warning('Found %s, which looks suitable for this '
                               'binary. Please use -i if you want to use '
                               'another image', k)
                return k
            except:
                pass

        raise CommandError('No suitable image available for this binary')

    def _get_or_download_image(self, image, download):
        img_json_path = self.image_path(image)

        try:
            return get_image_descriptor(img_json_path)
        except:
            if not download:
                raise

        logger.info('Image %s missing, attempting to download...', image)
        self.download_images([image])
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

    def _save_json_description(self, context):
        """
        Create a JSON description of the project.

        This information can be used by other commands.
        """
        logger.info('Creating JSON description')
        project_desc_path = os.path.join(self._project_dir, 'project.json')
        with open(project_desc_path, 'w') as f:
            s = json.dumps(context, sort_keys=True, indent=4)
            f.write(s)

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
                   os.path.join(self._project_dir, target_file))

    def _symlink_guest_tools(self):
        """
        Create a symlink to the guest tools directory.
        """
        guest_tools_path = self.install_path(
            'bin', CONSTANTS['guest_tools'][self._arch]
        )

        logger.info('Creating a symlink to %s', guest_tools_path)

        os.symlink(guest_tools_path,
                   os.path.join(self._project_dir, 'guest-tools'))

    def _symlink_guestfs(self, image_name):
        """
        Create a symlink to the guestfs directory.
        """
        guestfs_path = self.image_path(image_name, 'guestfs')
        if not os.path.exists(guestfs_path):
            logger.warn('%s does not exist, Vmi plugin may not run optimally',
                        guestfs_path)
            return False

        logger.info('Creating a symlink to %s', guestfs_path)
        os.symlink(guestfs_path,
                   os.path.join(self._project_dir, 'guestfs'))
        return True
