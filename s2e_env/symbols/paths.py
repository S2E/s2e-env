"""
Copyright (c) 2018 Cyberhaven

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

logger = logging.getLogger('paths')


def _convert_path_to_unix(path):
    if '\\' not in path:
        return path

    path = path.replace('\\', '/')
    if len(path) >= 3 and path[1:3] == ':/':
        path = path[2:]

    return path


def guess_target_path(search_paths, target):
    """
    Find the given binary file in the specified search paths.
    To accommodate Windows, this function also looks for the lower case version of the name.
    """
    if os.path.exists(target):
        return target

    if os.name != 'nt':
        target = _convert_path_to_unix(target)

    # os.path.join does not like concatenating two absolute paths
    if target[0] == '/':
        target = target[1:]

    tried = []
    bn = os.path.basename(target)

    # Try base name without the path prefix first, in case the file
    # ends up being stored in user locations. The prefixed path
    # is usually used as last resort within the guestfs folder.
    # TODO: scan all folders and detect conflicting files
    candidates = [bn, target]

    if bn.lower() != bn:
        candidates.append(bn.lower())

    if target.lower() != target:
        candidates.append(target.lower())

    for t in candidates:
        for sp in search_paths:
            p = os.path.join(sp, t)
            logger.debug('trying %s || %s || %s', sp, t, p)
            if os.path.exists(p):
                return p
            tried.append(p)

    raise Exception('Could not find %s' % ', '.join(tried))


def _guess_rel_path(search_paths, path):
    for sp in search_paths:
        # Go to the parent directory until the path is found
        cur_path = sp

        while cur_path and cur_path != '/':
            test_path = os.path.join(cur_path, path)
            if os.path.exists(test_path):
                return os.path.normpath(test_path)
            cur_path = os.path.dirname(cur_path)

    return None


def _splitall(path):
    """
    This function splits a path /a/b/c into a list [/,a,b,c]
    """

    allparts = []

    while True:
        parts = os.path.split(path)
        if parts[0] == path:
            allparts.insert(0, parts[0])
            break

        if parts[1] == path:
            allparts.insert(0, parts[1])
            break

        path = parts[0]
        allparts.insert(0, parts[1])

    return allparts


def guess_source_file_path(search_paths, path):
    """
    Look for the specified relative path among the search paths.
    This function will try all parent directories in each search paths
    until it finds the given path. This is useful to lookup source files
    when debug information only encodes relative paths.

    If the given path is absolute and does not exist, this function
    will strip prefixes until it finds a suffix that matches one of the search paths.
    This is useful when moving sources between machines and prefixes are different.

    The resulting path is normalized (i.e., all redundant ../ and ./ are stripped).
    This is important as lcov does not like paths that contain ../ or ./.

    If the path could not be resolved, just return it as is.
    """
    if os.path.exists(path):
        return path

    original_path = path

    if os.name != 'nt':
        path = _convert_path_to_unix(path)

    if os.path.isabs(path):
        # Try to strip prefixes until we find something
        components = _splitall(path)
        for i in range(0, len(components)):
            c = os.path.join(*components[i:])
            guessed_path = _guess_rel_path(search_paths, c)
            if guessed_path:
                return guessed_path

        return original_path

    guessed_path = _guess_rel_path(search_paths, path)
    if guessed_path:
        return guessed_path

    return original_path
