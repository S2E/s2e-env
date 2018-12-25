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


import logging
import os

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError
from s2e_env.utils.images import ImageDownloader, get_image_templates, \
        get_image_descriptor


logger = logging.getLogger('new_project')


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
        target = options.pop('target')
        config = self._configure(target, *args, **options)
        self._create(config, options['force'])

        instructions = self._get_instructions(config)
        if instructions:
            logger.success(instructions)

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

    def _create(self, config, force=False):
        """
        Create the actual project based on the given project configuration
        dictionary.
        """
        raise NotImplementedError('Subclasses of AbstractProject must provide '
                                  'a _create method')

    def _get_instructions(self, config):
        """
        Generate instructions for the user on how to use their newly-created
        project. These instructions should be returned as a string.
        """
        pass

    def _is_valid_image(self, target, os_desc):
        """
        Validate a target against a particular image description.

        This validation may vary depending on the target and image type.
        Returns ``True`` if the binary is valid and ``False`` otherwise.
        """
        pass

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

    def _guess_image(self, target, templates):
        """
        At this stage, images may not exist, so we get the list of images
        from images.json (in the guest-images repo) rather than from the images
        folder.
        """
        logger.info('No image was specified (-i option). Attempting to guess '
                    'a suitable image for a %s binary...', target.arch)

        for k, v in templates.iteritems():
            if self._is_valid_image(target, v['os']):
                logger.warning('Found %s, which looks suitable for this '
                               'binary. Please use -i if you want to use '
                               'another image', k)
                return k

        raise CommandError('No suitable image available for this target')

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
                   os.path.join(project_dir, 'guest-tools'))
