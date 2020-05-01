"""
Copyright (c) 2017 Cyberhaven

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

from sh import git, ErrorReturnCode
from s2e_env import CONSTANTS
from s2e_env.command import  CommandError


logger = logging.getLogger(__name__)


def git_clone(git_repo_url, git_repo_dir):
    try:
        logger.info('Fetching from %s to %s', git_repo_url, git_repo_dir)
        git.clone(git_repo_url, git_repo_dir, _out=sys.stdout,
                  _err=sys.stderr)
    except ErrorReturnCode as e:
        raise CommandError(e)


def git_clone_to_source(env_path, git_repo):
    git_url = CONSTANTS['repos']['url']

    git_repo_dir = os.path.join(env_path, 'source', git_repo)
    git_repo_url = '%s/%s' % (git_url, git_repo)
    git_clone(git_repo_url, git_repo_dir)
    logger.success('Fetched %s', git_repo)
