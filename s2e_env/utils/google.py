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
import urllib.parse

from alive_progress import alive_bar
import requests


logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 128


def _save_response_content(response, destination):
    with open(destination, 'wb') as f:
        length = int(response.headers.get('Content-Length'))
        logger.info('File size: %d bytes', length)
        with alive_bar(length) as progress:
            for chunk in response.iter_content(CHUNK_SIZE):
                # filter out keep-alive new chunks
                if chunk:
                    f.write(chunk)
                    # pylint: disable=not-callable
                    progress(len(chunk))


def _download(docid, destination):
    url = 'https://docs.google.com/uc?export=download'

    session = requests.Session()

    logger.info('Requesting %s with id=%s', url, docid)
    response = session.get(url, params={'id': docid, 'confirm':'t'}, stream=True)

    _save_response_content(response, destination)


def download(public_url, destination):
    o = urllib.parse.urlparse(public_url)
    q = urllib.parse.parse_qs(o.query)
    _download(q['id'], destination)
