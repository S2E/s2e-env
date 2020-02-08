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
import sys
import urllib.parse

import requests


logger = logging.getLogger(__name__)

CHUNK_SIZE = 32768

# Inspired from:
# http://stackoverflow.com/questions/25010369/wget-curl-large-file-from-google-drive

def _get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value

    return None


def _save_response_content(response, destination):
    bytes_count = 0
    next_count = 0
    with open(destination, 'wb') as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            # filter out keep-alive new chunks
            if chunk:
                bytes_count += len(chunk)
                next_count += len(chunk)
                f.write(chunk)

            if next_count > 1024 * 1024 * 10:
                sys.stdout.write('Downloaded %d bytes\r' % bytes_count)
                sys.stdout.flush()
                next_count = 0


def _download(docid, destination):
    url = 'https://docs.google.com/uc?export=download'

    session = requests.Session()

    logger.info('Requesting %s with id=%s', url, docid)
    response = session.get(url, params={'id': docid}, stream=True)
    token = _get_confirm_token(response)

    if token:
        logger.info('Sending confirmation token')
        params = {'id': docid, 'confirm': token}
        response = session.get(url, params=params, stream=True)

    _save_response_content(response, destination)


def download(public_url, destination):
    o = urllib.parse.urlparse(public_url)
    q = urllib.parse.parse_qs(o.query)
    _download(q['id'], destination)
