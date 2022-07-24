"""
Copyright (c) 2017 Cyberhaven
Copyright (c) 2017 Dependable Systems Laboratory, EPFL
Copyright (c) 2018 Adrian Herrera

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


from abc import abstractmethod
import json
import logging
import os
import shutil

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError
from s2e_env.utils.images import ImageDownloader, get_image_templates, \
        get_image_descriptor, select_guestfs, split_image_name, \
        check_host_incompatibility, select_best_image

from .utils import ConfigEncoder

logger = logging.getLogger('new_project')

# Paths
FILE_DIR = os.path.dirname(__file__)
LIBRARY_LUA_PATH = os.path.join(FILE_DIR, '..', '..', 'dat', 'library.lua')

SUPPORTED_TOOLS = ['pov', 'cfi', 'tickler']


def symlink_guest_tools(install_path, project_dir, img_desc):
    """
    Create a symlink to the guest tools directory.

    Args:
        install_path: path to S2E installation
        project_dir: The project directory.
        img_desc: A dictionary that describes the image that will be used,
                  from `$S2EDIR/source/guest-images/images.json`.
    """
    img_arch = img_desc['qemu_build']
    guest_tools_path = \
        os.path.join(install_path, 'bin', CONSTANTS['guest_tools'][img_arch])

    logger.info('Creating a symlink to %s', guest_tools_path)
    os.symlink(guest_tools_path,
               os.path.join(project_dir, CONSTANTS['guest_tools'][img_arch]))

    # Also link 32-bit guest tools for 64-bit guests.
    # This is required on Linux to have 32-bit s2e.so when loading 32-bit binaries
    if img_arch == 'x86_64':
        guest_tools_path_32 = \
            os.path.join(install_path, 'bin', CONSTANTS['guest_tools']['i386'])

        os.symlink(guest_tools_path_32,
                   os.path.join(project_dir, CONSTANTS['guest_tools']['i386']))


def symlink_guestfs(project_dir, guestfs_paths):
    """
    Create a symlink to the guestfs directory.
    """
    if len(guestfs_paths) > 1:
        for idx, path in enumerate(guestfs_paths):
            logger.info('Creating a symlink to %s', path)
            os.symlink(path, os.path.join(project_dir, f'guestfs{idx}'))
    else:
        path = guestfs_paths[0]
        logger.info('Creating a symlink to %s', path)
        os.symlink(path, os.path.join(project_dir, 'guestfs'))


def validate_arguments(options):
    """
    Check that arguments are consistent.
    """

    tools = options.get('tools', [])
    for tool in tools:
        if tool not in SUPPORTED_TOOLS:
            raise CommandError(f'The specified tool "{tool}" is not supported')

    options['enable_pov_generation'] = 'pov' in tools
    options['enable_cfi'] = 'cfi' in tools
    options['enable_tickler'] = 'tickler' in tools

    has_errors = False
    if options.get('single_path'):
        if options.get('use_seeds'):
            logger.error('Cannot use seeds in single-path mode')
            has_errors = True

        if options.get('enable_pov_generation'):
            logger.error('Cannot use POV generation in single-path mode')
            has_errors = True

        if '@@' in options.get('target_args', []):
            logger.error('Cannot use symbolic input in single-path mode')
            has_errors = True

    if has_errors:
        return False

    return True


class AbstractProject(EnvCommand):
    """
    An abstract class for creating S2E analysis projects.

    This class must be overridden and the following methods **must** be
    implemented:

      - ``_configure``
      - ``_create``

    The following methods may be optionally implemented:

      - ``_get_instructions``
      - ``_is_valid_image``

    ``AbstractProject`` provides helper methods for deciding on the virtual
    machine image to use.
    """

    def handle(self, *args, **options):
        # Generate a project config for the given target
        target = options.pop('target')
        config = self._configure(target, *args, **options)

        # Create the actual project (and all the required files).The location
        # of the newly-created project should be returned
        project_dir = self._create(config, options['force'])

        # Save the project descriptor in the project directory
        self._save_json_description(project_dir, config)

        # If the project comes with instructions, display them
        instructions = self._get_instructions(config)
        if instructions:
            logger.success(instructions)

    #
    # Abstract methods to overwrite
    #

    @abstractmethod
    def _configure(self, target, *args, **kwargs):
        """
        Generate the configuration dictionary that describes this project.

        Args:
            target: A ``Target`` object that represents the program under
                    analysis.

        Returns:
            A configuration ``dict``.
        """
        raise NotImplementedError('Subclasses of AbstractProject must provide '
                                  'a _configure method')

    @abstractmethod
    def _create(self, config, force=False):
        """
        Create the actual project based on the given project configuration
        dictionary in ``config``.

        Returns:
            The path to the directory where the project was created.
        """
        raise NotImplementedError('Subclasses of AbstractProject must provide '
                                  'a _create method')

    # pylint: disable=unused-argument
    # pylint: disable=no-self-use
    def _get_instructions(self, config):
        """
        Generate instructions for the user on how to use their newly-created
        project. These instructions should be returned as a string.
        """
        return ''

    def _is_valid_image(self, target, os_desc):
        """
        Validate a target against a particular image description.

        This validation may vary depending on the target and image type.
        Returns ``True`` if the binary is valid and ``False`` otherwise.
        """

    #
    # Image helper methods
    #

    def _select_image(self, target, image=None, download_image=True):
        """
        Select an image to use for this project.

        If an image was specified, use it. Otherwise select an image to use
        based on the target's architecture. If the image is not available, it
        may be downloaded.

        Returns:
            A dictionary that describes the image that will be used, based on
            the image's JSON descriptor.
        """
        # Load the image JSON description. If it is not given, guess the image
        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])
        img_templates = get_image_templates(img_build_dir)

        if not image:
            image = self._guess_image(target, img_templates)

        base_image_name, app_image_name = split_image_name(image)
        if app_image_name:
            # Don't do any validation on app images yet.
            return self._get_or_download_image(img_templates, image, download_image)

        if image not in img_templates:
            raise CommandError(f'Unknown guest image {image}. Run s2e image_build for a list of supported images.')

        supported_images = self.get_usable_images(target, img_templates)
        if not supported_images:
            raise CommandError('No suitable image available for this target.')

        if image not in supported_images:
            raise CommandError(f'Chosen image {image} is not compatbile with the target.')

        check_host_incompatibility(img_templates, base_image_name)
        return self._get_or_download_image(img_templates, image, download_image)

    def _guess_image(self, target, img_templates):
        """
        At this stage, images may not exist, so we get the list of images
        from images.json (in the guest-images repo) rather than from the images
        folder.
        """
        logger.info('No image was specified (-i option). Attempting to guess '
                    'a suitable image for a %s binary...', target.arch)

        usable_images = self.get_usable_images(target, img_templates)
        if not usable_images:
            raise CommandError('No suitable image available for this target')

        selected_image = select_best_image(img_templates, usable_images)

        logger.warning('Found %s, which looks suitable for this '
                       'binary. Please use -i if you want to use '
                       'another image', selected_image)

        return selected_image

    def get_usable_images(self, target, image_templates):
        """
        Returns all images suitable for this target.
        """
        images = []

        for k, v in image_templates.items():
            if self._is_valid_image(target, v['os']):
                images.append(k)

        return images

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

    #
    # Misc. helper methods
    #

    # pylint: disable=no-self-use
    def _save_json_description(self, project_dir, config):
        """
        Create a JSON description of the project.

        This information can be used by other commands.
        """
        logger.info('Creating JSON description')

        # Make sure that the JSON description **always** contains the project
        # directory
        config['project_dir'] = project_dir

        config_copy = config.copy()

        # Do not hard-code image settings in the JSON, as they may change
        # when images are rebuilt. Instead, always use latest images.json
        # in guest-images repo. This avoids forcing users to create new projects
        # everytime guest image parameters change.
        config_copy['image'] = os.path.dirname(config['image']['path'])

        project_desc_path = os.path.join(project_dir, 'project.json')
        with open(project_desc_path, 'w', encoding='utf-8') as f:
            s = json.dumps(config_copy, sort_keys=True, indent=4, cls=ConfigEncoder)
            f.write(s)

    # pylint: disable=no-self-use
    def _copy_lua_library(self, project_dir):
        """
        Copy library.lua into the project directory.

        library.lua contains a number of helper methods that can be used by the
        S2E Lua configuration file.
        """
        shutil.copy(LIBRARY_LUA_PATH, project_dir)

    # pylint: disable=no-self-use
    def _symlink_project_files(self, project_dir, *files):
        """
        Create symlinks to the files that compose the project.
        """
        for f in files:
            target_file = os.path.basename(f)

            source_path = os.path.abspath(f)
            symlink_path = os.path.join(project_dir, target_file)
            if os.path.realpath(source_path) != os.path.realpath(symlink_path):
                logger.info('Creating a symlink to %s', f)
                os.symlink(source_path, symlink_path)
            else:
                logger.info('Not creating a symlink to %s, source and destination files are the same', f)

    def _symlink_guest_tools(self, project_dir, img_desc):
        return symlink_guest_tools(self.install_path(), project_dir, img_desc)

    def _select_guestfs(self, img_desc):
        return select_guestfs(self.image_path(), img_desc)

    # pylint: disable=no-self-use
    def _symlink_guestfs(self, project_dir, guestfs_paths):
        return symlink_guestfs(project_dir, guestfs_paths)

    # pylint: disable=no-self-use
    def _translate_target_path_to_guestfs(self, target_path, guestfs_paths):
        """
        This function converts a target path that is located in a guestfs folder to an absolute
        guest path.

        :param target_path: The target path to convert
        :param guestfs_paths: The list if guestfs paths to inspect.
        :return:
        """
        if not target_path:
            return None

        real_target_path = os.path.realpath(target_path)

        for guestfs_path in guestfs_paths:
            # target and guestfs may be symlinks, need to compare actual path
            real_guestfs_path = os.path.realpath(guestfs_path)
            paths = [real_target_path, real_guestfs_path]
            common = os.path.commonpath(paths)
            if real_guestfs_path in common:
                return f'/{os.path.relpath(real_target_path, real_guestfs_path)}'

        # Check if that target_path is in the correct guestfs
        if real_target_path.startswith(os.path.realpath(self.image_path())):
            logger.error('%s seems to be located in a guestfs directory.', target_path)
            logger.error('However, the selected image uses the following directories:')
            for path in guestfs_paths:
                logger.error('  * %s', path)

            raise CommandError('Please check that you selected the proper guest image (-i option) '
                               'and/or the binary in the right guestfs directory.')

        return None
