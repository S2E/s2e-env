"""
Copyright (c) 2020, Vitaly Chipounov

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

import datetime
import logging
import os
import subprocess

from s2e_env.command import EnvCommand, CommandError
from s2e_env.utils.templates import render_template, DEFAULT_TEMPLATES_DIR

logger = logging.getLogger('new_plugin')


def _inject_plugin_path(makefile, plugin_path):
    with open(makefile, 'r', encoding='utf-8') as fp:
        lines = fp.readlines()

    out_lines = []
    state = 0
    for line in lines:
        line = line.rstrip()

        if plugin_path in line:
            logger.warning('%s already set in %s', plugin_path, makefile)
            return ''.join(lines)

        if not state:
            if 'add_library(' in line:
                state = 1

        if state == 1 and 's2eplugins' in line:
            state = 2

        out_lines.append(line)

        if state == 2:
            out_lines.append('')
            out_lines.append(f'    {plugin_path}')
            state = 3

    return '\n'.join(out_lines) + '\n'


def _get_user_name():
    try:
        username = subprocess.check_output(['git', 'config', 'user.name']).decode()
    except subprocess.CalledProcessError:
        username = ''

    return username.strip()


class Command(EnvCommand):
    """
    Create a new S2E plugin.
    """

    help = 'Create a new S2E plugin.'

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument('plugin_name', nargs=1,
                            help='The name of the plugin. Can be of the form Dir1/Dir2/PluginName.')

        parser.add_argument('--use-guest-interface',
                            help='Generates the interface to allow guests to communicate with the plugin',
                            default='true', action='store_true')

        parser.add_argument('--force',
                            help='Overwrites existing plugin',
                            action='store_true')

        parser.add_argument('--author-name',
                            help='The plugin author name (uses git config "user.name" if not provided).')

    # pylint: disable=too-many-locals
    def handle(self, *args, **options):
        s2e_src_dir = self.env_path('source', 's2e', 'libs2eplugins', 'src')
        s2e_plugins_dir = self.env_path(s2e_src_dir, 's2e', 'Plugins')

        plugin_name = os.path.basename(options['plugin_name'][0])
        plugin_rel_dir = os.path.dirname(options['plugin_name'][0])
        author = options['author_name'] or _get_user_name()

        if not author:
            raise CommandError('Could not determine your name. Run this command again and provide a '
                               '"--author-name NAME" or set it with "git config user.name NAME"')

        if not os.path.exists(s2e_src_dir):
            raise CommandError(f'{s2e_src_dir} does not exist. Make sure the source code is initialized properly.')

        if plugin_rel_dir:
            if os.path.isabs(plugin_rel_dir):
                raise CommandError(f'The plugin name must be relative to the {s2e_plugins_dir} directory.')
            output_dir = os.path.join(s2e_plugins_dir, plugin_rel_dir)
            os.makedirs(output_dir, exist_ok=True)
        else:
            output_dir = s2e_plugins_dir

        logger.info('Creating plugin in %s', output_dir)

        cpp_plugin_path = os.path.join(output_dir, f'{plugin_name}.cpp')
        header_plugin_path = os.path.join(output_dir, f'{plugin_name}.h')

        if os.path.exists(cpp_plugin_path) or os.path.exists(header_plugin_path):
            if not options['force']:
                raise CommandError('The specified plugin already exists. Use --force to overwrite.')

        context = {
            'author': {
                'name': author,
                'year': datetime.datetime.now().year
            },
            'plugin': {
                'name': plugin_name,
                'description': 'Describe what the plugin does here'
            },
            'use_guest_interface': options['use_guest_interface']
        }

        template_dir = os.path.join(DEFAULT_TEMPLATES_DIR, 'plugin_creation')
        render_template(context, 'plugin.cpp.template', cpp_plugin_path, template_dir)
        render_template(context, 'plugin.h.template', header_plugin_path, template_dir)

        # Update CMakeLists.txt
        rel_plugin_path = os.path.relpath(cpp_plugin_path, s2e_src_dir)
        s2e_plugins_makefile = self.env_path('source', 's2e', 'libs2eplugins', 'src', 'CMakeLists.txt')
        ret = _inject_plugin_path(s2e_plugins_makefile, rel_plugin_path)

        with open(s2e_plugins_makefile, 'w', encoding='utf-8') as fp:
            fp.write(ret)

        logger.success(
            'Plugin successfully created. Please rebuild S2E and activate it in s2e-config.lua by adding these lines:\n'
            + f'\nadd_plugin("{plugin_name}")\n\n'
            + f'pluginsConfig.{plugin_name} = {{\n'
            + '  -- Set here your plugin configuration\n'
            + '}'
        )
