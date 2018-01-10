"""
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


import os
import stat

from jinja2 import Environment, FileSystemLoader

from .memoize import memoize


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')


def _datetimefilter(value, format_='%H:%M %d-%m-%Y'):
    """
    Jinja2 filter.
    """
    return value.strftime(format_)


@memoize
def _init_template_env(templates_dir=TEMPLATES_DIR):
    """
    Initialize the jinja2 templating environment using the templates in the
    given directory.
    """
    env = Environment(loader=FileSystemLoader(templates_dir),
                      autoescape=False)
    env.filters['datetimefilter'] = _datetimefilter

    return env


def render_template(context, template, path=None, executable=False):
    """
    Renders the ``template`` template with the given ``context``. The result is
    written to ``path``. If ``path`` is not specified, the result is
    returned as a string
    """
    env = _init_template_env()
    data = env.get_template(template).render(context)

    if not path:
        return data

    with open(path, 'w') as f:
        f.write(data)

    if executable:
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IEXEC)

    return True
