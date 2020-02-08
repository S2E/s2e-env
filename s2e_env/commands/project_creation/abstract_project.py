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
        get_image_descriptor


logger = logging.getLogger('new_project')

# Paths
FILE_DIR = os.path.dirname(__file__)
LIBRARY_LUA_PATH = os.path.join(FILE_DIR, '..', '..', 'dat', 'library.lua')


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

        return self._get_or_download_image(img_templates, image, download_image)

    def _guess_image(self, target, img_templates):
        """
        At this stage, images may not exist, so we get the list of images
        from images.json (in the guest-images repo) rather than from the images
        folder.
        """
        logger.info('No image was specified (-i option). Attempting to guess '
                    'a suitable image for a %s binary...', target.arch)

        images = self.get_usable_images(target, img_templates)
        if not images:
            raise CommandError('No suitable image available for this target')

        image = images[0]
        logger.warning('Found %s, which looks suitable for this '
                       'binary. Please use -i if you want to use '
                       'another image', image)

        return image

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
        with open(project_desc_path, 'w') as f:
            s = json.dumps(config_copy, sort_keys=True, indent=4)
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
            logger.info('Creating a symlink to %s', f)
            target_file = os.path.basename(f)
            os.symlink(os.path.abspath(f), os.path.join(project_dir, target_file))

    def _symlink_guest_tools(self, project_dir, img_desc):
        """
        Create a symlink to the guest tools directory.

        Args:
            project_dir: The project directory.
            img_desc: A dictionary that describes the image that will be used,
                      from `$S2EDIR/source/guest-images/images.json`.
        """
        img_arch = img_desc['qemu_build']
        guest_tools_path = \
            self.install_path('bin', CONSTANTS['guest_tools'][img_arch])

        logger.info('Creating a symlink to %s', guest_tools_path)
        os.symlink(guest_tools_path,
                   os.path.join(project_dir, CONSTANTS['guest_tools'][img_arch]))

        # Also link 32-bit guest tools for 64-bit guests.
        # This is required on Linux to have 32-bit s2e.so when loading 32-bit binaries
        if img_arch == 'x86_64':
            guest_tools_path_32 = \
                self.install_path('bin', CONSTANTS['guest_tools']['i386'])

            os.symlink(guest_tools_path_32,
                       os.path.join(project_dir, CONSTANTS['guest_tools']['i386']))


    def _select_guestfs(self, img_desc):
        """
        Select the guestfs to use, based on the chosen virtual machine image.

        Args:
            img_desc: An image descriptor read from the image's JSON
            description.

        Returns:
            The path to the guestfs directory, or `None` if a suitable guestfs
            was not found.
        """
        image_dir = os.path.dirname(img_desc['path'])
        guestfs_path = self.image_path(image_dir, 'guestfs')

        return guestfs_path if os.path.exists(guestfs_path) else None

    # pylint: disable=no-self-use
    def _symlink_guestfs(self, project_dir, guestfs_path):
        """
        Create a symlink to the guestfs directory.
        """
        logger.info('Creating a symlink to %s', guestfs_path)
        os.symlink(guestfs_path, os.path.join(project_dir, 'guestfs'))
