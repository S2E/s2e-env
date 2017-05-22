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


import logging
import os
import sys

from sh import tar, ErrorReturnCode

from s2e_env.command import CommandError
from . import google


logger = logging.getLogger(__name__)


def _download(url, path):
    """
    Download a file from the Google drive and save it at the given ``path``.
    """
    logger.info('Downloading %s', url)
    google.download(url, path)


def _decompress(path):
    """
    Decompress a .tar.xz file at the given path.

    The decompressed data will be located in the same directory as ``path``.
    """
    logger.info('Decompressing %s', path)
    try:
        tar(extract=True, xz=True, verbose=True, file=path,
            directory=os.path.dirname(path), _fg=True, _out=sys.stdout,
            _err=sys.stderr)
    except ErrorReturnCode as e:
        raise CommandError(e)


class ImageDownloader(object):
    """
    Downloads images from a given URL to a given destination directory.

    Attributes:
        _templates: A dictionary containing the image template information, as
                    defined in the S2E guest-images repo.
    """

    def __init__(self, templates):
        self._templates = templates

    def download_images(self, image_names, dest_dir):
        """
        Download the images listed in ``image_names`` to ``dest_dir``.
        """
        for image in image_names:
            self._download_image(image, dest_dir)

    def _download_image(self, image, dest_dir):
        image_desc = self._templates.get(image)
        if not image_desc:
            raise CommandError('%s is not a valid image name' % image)

        url = self._templates[image].get('url')
        if not url:
            raise CommandError('The image %s has not downloadable archive' % image)

        dest_file = os.path.join(dest_dir, '%s.tar.xz' % image)
        _download(url, dest_file)
        _decompress(dest_file)
