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


import json
import logging
import os
import sys

# pylint: disable=no-name-in-module
from sh import tar, ErrorReturnCode

from s2e_env import CONSTANTS
from s2e_env.command import CommandError
from . import google


logger = logging.getLogger(__name__)

#
# Image downloading
#


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
            directory=os.path.dirname(path), _out=sys.stdout,
            _err=sys.stderr)
    except ErrorReturnCode as e:
        raise CommandError(e)


class ImageDownloader:
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


#
# Image utility functions
#
def _validate_version(descriptor, filename):
    version = descriptor.get('version')
    required_version = CONSTANTS['required_versions']['guest_images']
    if version != required_version:
        raise CommandError('%s versions do not match (s2e-env: %.2f, image: '
                           '%.2f). Make sure that you have the correct '
                           'revision of the guest-images repository' %
                           (filename, required_version, version))


def _get_templates(img_build_dir, filename, key):
    images = os.path.join(img_build_dir, filename)

    try:
        with open(images, 'r') as f:
            template_json = json.load(f)
    except:
        raise CommandError('Could not parse %s. Something is wrong with the '
                           'environment' % images)

    _validate_version(template_json, images)

    return template_json[key]


def get_image_templates(img_build_dir):
    return _get_templates(img_build_dir, 'images.json', 'images')


def get_app_templates(img_build_dir):
    return _get_templates(img_build_dir, 'apps.json', 'apps')


def get_image_descriptor(image_dir):
    """
    Load the image's JSON descriptor.

    Args:
        image_dir: directory containing a built image.

    Returns:
        A dictionary that describes the given image.
    """
    img_json_path = os.path.join(image_dir, 'image.json')

    try:
        with open(img_json_path, 'r') as f:
            ret = json.load(f)
            _validate_version(ret, img_json_path)
            ret['path'] = os.path.join(image_dir, 'image.raw.s2e')

            return ret
    except CommandError:
        raise
    except Exception as e:
        raise CommandError('Unable to open image description %s: %s' %
                           (img_json_path, e))


def get_all_images(templates, app_templates):
    """
    Builds the list of all available images and image groups.
    Returns a tuple (images, groups, image_descriptors).
    """
    images = set()
    groups = {}
    descriptions = {}

    for base_image, desc in templates.items():
        images.add(base_image)
        group = desc['image_group']
        if group not in groups:
            groups[group] = set()
        groups[group].add(base_image)
        descriptions[base_image] = desc

    for app, desc in app_templates.items():
        for base_image in desc.get('base_images'):
            if base_image not in images:
                raise CommandError(
                    f'App {app} requires {base_image}, but it does not exist.'
                    ' Check that images.json and app.json are valid.'
                )
            key = f'{base_image}/{app}'
            images.add(key)
            descriptions[key] = desc

            for group in desc.get('image_groups'):
                if group not in groups:
                    groups[group] = set()
                groups[group].add(key)

    groups['all'] = images

    return images, groups, descriptions


def translate_image_name(images, image_groups, image_names):
    """
    Translates a set of user-friendly image names into a set of actual image
    names that can be sent to the makefile. For example, "all" will be
    translated to the set of all images, while "windows" and "linux" will be
    translated to the appropriate subset of Windows or Linux images.
    """
    ret = set()

    for image_name in image_names:
        if image_name in images:
            ret.add(image_name)
        elif image_name in image_groups:
            ret = ret.union(image_groups[image_name])
        else:
            raise CommandError(f'{image_name} does not exist')

    return ret


def select_guestfs(image_path, img_desc):
    """
    Select the guestfs to use, based on the chosen virtual machine image.

    Args:
        image_path: Path to S2E images
        img_desc: An image descriptor read from the image's JSON
        description.

    Returns:
        The paths to the guestfs directories, or `None` if a suitable guestfs
        was not found. This may return up to two guestfs paths if the specified
        image is an app image. The app guestfs path must come before the guestfs
        for the base image, s2e-config.lua assumes this.
    """
    ret = []
    image_dir = os.path.dirname(img_desc['path'])
    guestfs_path = os.path.join(image_path, image_dir, 'guestfs')
    if os.path.exists(guestfs_path):
        ret.append(guestfs_path)

    if 'apps' in img_desc:
        # We have an app image, also try to get the guestfs for the base one
        guestfs_path = os.path.abspath(os.path.join(image_path, image_dir, '..', 'guestfs'))
        if os.path.exists(guestfs_path):
            ret.append(guestfs_path)

    return ret
