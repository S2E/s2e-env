"""
Copyright (c) 2019 Cyberhaven

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
import multiprocessing
import multiprocessing.dummy
import signal
import subprocess
import os
import stat
import sys
import yaml

import psutil
import sh

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError
from s2e_env.manage import call_command
from s2e_env.commands.project_creation import Target
from s2e_env.commands.run import send_signal_to_children_on_exit
from s2e_env.utils.images import get_image_templates
from s2e_env.utils.templates import render_template

logger = logging.getLogger('testsuite')


def _get_tests(testsuite_root):
    tests = []

    for fn in os.listdir(testsuite_root):
        path = os.path.join(testsuite_root, fn)
        if fn.startswith('.') or not os.path.isdir(path):
            continue
        tests.append(fn)

    return tests


def _get_run_test_scripts(project_root):
    tests = []

    for fn in os.listdir(project_root):
        path = os.path.join(project_root, fn)
        if not fn.startswith('testsuite_'):
            continue

        run_tests_path = os.path.join(project_root, path, 'run-tests')
        if not os.path.exists(run_tests_path):
            logger.warning('%s does not exist, skipping test project %s', run_tests_path, fn)

        tests.append(run_tests_path)

    return tests


def _build_test(s2e_config, s2e_source_root, test_root):
    s2e_inc_dir = os.path.join(s2e_source_root, 'guest', 'common', 'include')
    env = os.environ.copy()
    env['CFLAGS'] = '-I%s' % s2e_inc_dir
    env['S2ESRC'] = s2e_source_root
    env['WINDOWS_BUILD_HOST'] = s2e_config.get('windows_build_server', {}).get('host', '')
    env['WINDOWS_BUILD_USER'] = s2e_config.get('windows_build_server', {}).get('user', '')
    make = sh.Command('make').bake('-C', test_root, 'all', _out=sys.stdout, _err=sys.stderr, _fg=True, _env=env)
    make()


def _read_config(test_root, s2e_images_root):
    cfg_file = os.path.join(test_root, 'config.yml')
    ctx = {
        's2e_images': s2e_images_root
    }
    rendered = render_template(ctx, cfg_file, templates_dir='/')
    return yaml.safe_load(rendered)['test']


def _call_post_project_gen_script(test_dir, test_config, options):
    script = test_config.get('build-options', {}).get('post-project-generation-script', None)
    if not script:
        return

    script = os.path.join(test_dir, script)
    if not os.path.exists(script):
        raise CommandError('%s does not exist' % script)

    env = os.environ.copy()
    env['PROJECT_DIR'] = options['project_path']
    env['TARGET'] = options['target'].path
    env['TESTSUITE_ROOT'] = options['testsuite_root']

    cmd = sh.Command(script).bake(_out=sys.stdout, _err=sys.stderr, _fg=True, _env=env)
    cmd()


class TestsuiteGenerator(EnvCommand):
    def __init__(self):
        super(TestsuiteGenerator, self).__init__()
        self._cmd_options = {}

    def _get_image_templates(self):
        img_build_dir = self.source_path(CONSTANTS['repos']['images']['build'])
        return get_image_templates(img_build_dir)

    def _generate_run_tests(self, ts_dir, test, script_template, options):
        ctx = {
            'test_dir': os.path.join(ts_dir, test),
            'project_name': options['name'],
            'creation_time': str(datetime.datetime.now())
        }

        run_tests_template = '%s/%s' % (test, script_template)
        run_tests = render_template(ctx, run_tests_template, templates_dir=ts_dir)

        run_tests_path = os.path.join(self.projects_path(options['name']), 'run-tests')
        with open(run_tests_path, 'w') as fp:
            fp.write(run_tests)

        st = os.stat(run_tests_path)
        os.chmod(run_tests_path, st.st_mode | stat.S_IEXEC)

    def _must_generate_test(self, test_name, test_config):
        build_options = test_config.get('build-options', {})
        if build_options.get('windows-build-server', False):
            if not self._cmd_options.get('with_windows_build'):
                # Skip tests that require a windows build server if instructed
                logger.warning('Skipping test %s, because it requires a Windows build machine', test_name)
                return False

            host = self.config.get('windows_build_server', {}).get('host', '')
            user = self.config.get('windows_build_server', {}).get('user', '')
            if not host or not user:
                msg = 'Test %s requires a Windows build server.\n' \
                      'Please check that your s2e.yaml file contains a valid Windows build server ' \
                      'configuration. Refer to the following page for details on how to set up the server:\n' \
                      'http://s2e.systems/docs/WindowsEnvSetup.html' % test_name
                raise CommandError(msg)

        return True

    # pylint: disable=too-many-locals
    def _handle_test(self, test_root, test, test_config, img_templates):
        ts_dir = self.source_path('s2e', 'testsuite')

        if os.path.exists(os.path.join(test_root, 'Makefile')):
            _build_test(self._config, self.source_path('s2e'), test_root)

        blacklisted_images = set(test_config.get('blacklisted-images', []))
        target_images = set(test_config.get('target-images', []))

        for target_name in test_config['targets']:
            target_path = os.path.join(test_root, target_name)
            target = Target.from_file(target_path)
            project = target.initialize_project()
            images = project.get_usable_images(target, img_templates)

            for image_name in images:
                if image_name in blacklisted_images:
                    logger.warning('%s is blacklisted, skipping tests for that image', image_name)
                    continue

                if target_images and image_name not in target_images:
                    logger.debug('%s is not in target-images, skipping', image_name)
                    continue

                name = 'testsuite_%s_%s_%s' % (test, os.path.basename(target_name), image_name)
                options = {
                    'image': image_name,
                    'name': name,
                    'target': target,
                    'target_args': test_config.get('target_arguments', []),
                    'force': True,
                    'project_path': self.projects_path(name),
                    'testsuite_root': ts_dir
                }
                options.update(test_config.get('options', []))

                call_command(project, *[], **options)

                scripts = test_config.get('scripts', {})
                run_tests_template = scripts.get('run_tests', 'run-tests.tpl')
                self._generate_run_tests(ts_dir, test, run_tests_template, options)
                _call_post_project_gen_script(test_root, test_config, options)


    def _get_tests(self):
        ts_dir = self.source_path('s2e', 'testsuite')
        if not os.path.isdir(ts_dir):
            raise CommandError('%s does not exist. Please check that you updated the S2E source' % ts_dir)

        tests = self._cmd_options['tests']
        if not tests:
            tests = _get_tests(ts_dir)

        return tests


    def handle(self, *args, **options):
        logger.info('Generating testsuite...')
        self._cmd_options = options

        img_templates = self._get_image_templates()
        ts_dir = self.source_path('s2e', 'testsuite')
        tests = self._get_tests()

        for test in tests:
            test_root = os.path.join(ts_dir, test)
            if not os.path.isdir(test_root):
                logger.error('%s is not a valid test directory', test_root)
                continue

            test_config = _read_config(test_root, self.image_path())
            if not self._must_generate_test(test, test_config):
                continue

            self._handle_test(test_root, test, test_config, img_templates)


class TestsuiteLister(EnvCommand):
    def handle(self, *args, **options):
        ts_dir = self.source_path('s2e', 'testsuite')
        if not os.path.isdir(ts_dir):
            logger.error('%s does not exist. Please check that you updated the S2E source', ts_dir)
            return

        tests = _get_tests(ts_dir)
        if not tests:
            logger.warning('There are no tests available')
            return

        logger.info('Available tests')
        for test in tests:
            test_root = os.path.join(ts_dir, test)

            cfg_file = os.path.join(test_root, 'config.yml')
            with open(cfg_file, 'r') as fp:
                config = yaml.safe_load(fp)['test']

            logger.info('%-25s: %s', test, config['description'])


def _get_max_instances(**options):
    if not options.get('instances', 0):
        # Determine optimal number of cores based on available memory
        cpus = psutil.cpu_count()
        mem = psutil.virtual_memory().available
        logger.info('The system has %d CPUs and %d GB of available RAM', cpus, mem / (1 << 30))

        logger.info('Average memory usage per S2E instance: %d GB',
                    TestsuiteRunner.AVERAGE_S2E_MEM_USAGE / (1 << 30))
        max_instances = int(mem / TestsuiteRunner.AVERAGE_S2E_MEM_USAGE)
        return min(cpus, max_instances)

    return options.get('instances')


class TestsuiteRunner(EnvCommand):
    """
    This class runs the S2E testsuite.
    """

    AVERAGE_S2E_MEM_USAGE = 3 * 1024 * 1024 * 1024

    def call_script(self, state, script):
        logger.info('Starting %s', script)
        env = os.environ.copy()
        env['S2EDIR'] = self.env_path()

        stdout = os.path.join(os.path.dirname(script), 'stdout.txt')
        stderr = os.path.join(os.path.dirname(script), 'stderr.txt')

        start_time = datetime.datetime.now()

        with open(stdout, 'w') as so:
            with open(stderr, 'w') as se:
                status = None
                try:
                    subprocess.check_call([script], env=env, stdout=so, stderr=se)
                    status = 'SUCCESS'
                except Exception:
                    status = 'FAILURE'
                finally:
                    end_time = datetime.datetime.now()
                    diff_time = end_time - start_time
                    ms = divmod(diff_time.total_seconds(), 60)
                    state['completed'] += 1
                    logger.info('[%d/%d %02d:%02d] %s: %s',
                                state['completed'], state['num_tests'], ms[0], ms[1], status, script)
                    if status == 'FAILURE':
                        logger.error('   Check %s for details', stdout)
                        logger.error('   Check %s for details', stderr)

    def handle(self, *args, **options):
        logger.info('Running testsuite')

        actual_instances = _get_max_instances(**options)

        logger.info('Running %d tests in parallel', actual_instances)

        # Compute the tests to run
        test_scripts = _get_run_test_scripts(self.projects_path())
        scripts_to_run = test_scripts

        # Filter out tests we don't want to run.
        # The test name here is actually a substring of the project name.
        # This would also allow filtering by image name or any other part the project name.
        # By default, all tests are run.
        selected_tests = options['tests']
        if selected_tests:
            scripts_to_run = []
            for test in selected_tests:
                for script in test_scripts:
                    if test in script:
                        scripts_to_run.append(script)

        if not scripts_to_run:
            logger.error('Could not find any tests to run. Please generate the testsuite first (s2e testsuite generate)'
                         ' and check that the specified test exists.')
            return

        send_signal_to_children_on_exit(signal.SIGKILL)

        pool = multiprocessing.dummy.Pool(actual_instances)

        try:
            state = {
                'completed': 0,
                'num_tests': len(scripts_to_run)
            }

            r = [pool.apply_async(self.call_script, (state, script,)) for script in scripts_to_run]
            pool.close()

            # This works around a bug in Python 2.7, which prevents pool.join() from
            # being interrupted by ctrl + c.
            for item in r:
                item.wait(timeout=9999999)

        except KeyboardInterrupt:
            logger.warning('Terminating testsuite (CTRL+C)')
            pool.terminate()
        finally:
            pool.join()


class Command(EnvCommand):
    """
    Generates and run the S2E testsuite.
    """

    help = 'Generates and runs S2E\'s testsuite'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(help='Testsuite action',
                                           dest='command')

        gen_ts_parser = subparsers.add_parser('generate', cmd=TestsuiteGenerator(),
                                              help='Generate a testsuite')

        gen_ts_parser.add_argument('--no-windows-build', dest='with_windows_build', action='store_false',
                                   default='true', help='Skip tests that require a Windows build server')

        gen_ts_parser.add_argument('tests', nargs='*', help='Tests to generate (all if empty)')

        run_ts_parser = subparsers.add_parser('run', cmd=TestsuiteRunner(),
                                              help='Run the testsuite')

        run_ts_parser.add_argument('--instance-count', dest='instances', type=int,
                                   default=0, help='How many instances to run in parallel')

        run_ts_parser.add_argument('tests', nargs='*', help='Tests to run (all if empty)')

        subparsers.add_parser('list', cmd=TestsuiteLister(),
                              help='Display available tests')

        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        command = options.pop('command', ())

        if command == 'generate':
            call_command(TestsuiteGenerator(), *args, **options)
        elif command == 'run':
            call_command(TestsuiteRunner(), *args, **options)
        elif command == 'list':
            call_command(TestsuiteLister(), *args, **options)
        else:
            raise CommandError('Invalid command %s' % command)
