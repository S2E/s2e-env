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


import argparse
import ctypes.util
import datetime
import json
import logging
import os
import shlex
import signal
import subprocess
import sys
from threading import Thread
import time

from s2e_env.command import ProjectCommand, CommandError
from s2e_env.server import CGCInterfacePlugin
from s2e_env.server import QMPTCPServer, QMPConnectionHandler
from s2e_env.server.collector_threads import CollectorThreads
from s2e_env.server.threads import terminating, terminate
from s2e_env.tui.tui import Tui
from s2e_env.utils.log import log_to_file


logger = logging.getLogger('run')
libc = ctypes.CDLL(ctypes.util.find_library('c'))

s2e_main_process = None


def send_signal_to_children_on_exit(sig):
    # Make sure that s2e would get killed if the parent process crashes
    # 1 = PR_SET_PDEATHSIG
    libc.prctl(1, sig, 0, 0, 0)


def _s2e_preexec():
    # Collect core dumps for S2E
    # resource.setrlimit(resource.RLIMIT_CORE, (-1, -1))

    send_signal_to_children_on_exit(signal.SIGTERM)


def _has_s2e_processes(pid):
    try:
        os.killpg(pid, 0)
        return True
    except OSError:
        return False


def _terminate_s2e():
    terminate()

    # First, send SIGTERM to S2E process group
    if not s2e_main_process:
        return

    logger.warning('Sending SIGTERM to S2E process group')

    try:
        os.killpg(s2e_main_process.pid, signal.SIGTERM)
    except OSError:
        return

    s2e_main_process.poll()

    # Give S2E time to quit
    logger.warning('Waiting for S2E processes to quit...')
    for _ in range(15):
        if not _has_s2e_processes(s2e_main_process.pid):
            logger.warning('All S2E processes terminated, exiting.')
            return
        time.sleep(1)

    # Second, kill s2e process group and all processes in its cgroup
    logger.warning('Sending SIGKILL to S2E process group')
    os.killpg(s2e_main_process.pid, signal.SIGKILL)
    s2e_main_process.wait()


def _sigterm_handler(signum=None, _=None):
    logger.warning('Got signal %s, terminating S2E', signum)
    _terminate_s2e()


def _wait_for_termination(timeout):
    if timeout:
        cnt = timeout * 60

    while not terminating():
        if timeout:
            if not cnt:
                return
            cnt = cnt-1
        time.sleep(1)


class S2EThread(Thread):
    # pylint: disable=too-many-arguments
    def __init__(self, args, env, cwd, stdout, stderr):
        super().__init__()
        self._args = args
        self._env = env
        self._cwd = cwd
        self._stdout = stdout
        self._stderr = stderr

    def run(self):
        # Launch s2e
        # pylint: disable=subprocess-popen-preexec-fn
        global s2e_main_process

        # pylint: disable=consider-using-with
        s2e_main_process = subprocess.Popen(
            self._args, preexec_fn=_s2e_preexec, env=self._env, cwd=self._cwd,
            stdout=self._stdout,
            stderr=self._stderr
        )

        # Wait until all processes in the S2E cgroup terminate
        s2e_main_process.wait()

        returncode = s2e_main_process.returncode
        while True:
            if not _has_s2e_processes(s2e_main_process.pid):
                break
            time.sleep(1)

        if self._stdout != sys.stdout:
            self._stdout.close()
        if self._stderr != sys.stderr:
            self._stderr.close()

        terminate()
        logger.info('S2E terminated with code %d', returncode)

        return returncode


class Command(ProjectCommand):
    help = 'Runs a project in S2E'

    _legend = {
        'binaries': 'Binary name(s)',
        'run_time': 'Run time (s)',
        'core_count': '# instances (current/max)',
        'states': 'Number of states',
        'completed_states': 'Number of states completed',
        'completed_seeds': 'Completed seeds',
        'covered_bbs': 'Covered basic blocks',
        'num_crashes': 'Number of crashes',
        'pov1': 'Type 1 POVs',
        'pov2': 'Type 2 POVs',
    }

    _layout = [
        'binaries',
        'run_time',
        'core_count',
        'states',
        'completed_states',
        'completed_seeds',
        'covered_bbs',
        'num_crashes',
        'pov1',
        'pov2'
    ]

    def __init__(self):
        super().__init__()
        self._start_time = None
        self._cgc = False

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument('project_args', nargs=argparse.REMAINDER,
                            help='Optional arguments to the S2E launcher script')
        parser.add_argument('-c', '--cores', required=False, default=1,
                            type=int, help='Number of cores to run S2E on')
        parser.add_argument('-n', '--no-tui', required=False,
                            action='store_true', help='Disable text UI')
        parser.add_argument('-t', '--timeout', required=False, default=None,
                            type=int, help='Terminate S2E after the timeout '
                                           '(in minutes) expires. This option '
                                           'has no effect when the TUI is enabled')

    # TODO: split this method
    def handle(self, *args, **options):
        no_tui = options['no_tui']

        # Port 0 tells the systems to dynamically allocate a free port
        qmp_socket = ('127.0.0.1', 0)

        analysis = {'output_path': self.project_path()}
        self._start_time = datetime.datetime.now()
        self._cgc = 'cgc' in self.image['os']['name']
        qmp_server = None

        try:
            logger.info('Starting service threads')
            CollectorThreads.start_threads()
            qmp_server = QMPTCPServer(qmp_socket, QMPConnectionHandler)
            qmp_server.analysis = analysis
            qmp_server_thread = Thread(target=qmp_server.serve_forever,
                                       name='QMPServerThread')
            qmp_server_thread.start()

            for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT):
                signal.signal(s, _sigterm_handler)

            if not no_tui:
                # pylint: disable=consider-using-with
                stdout = open(self.project_path('stdout.txt'), 'w', encoding='utf-8')

                # pylint: disable=consider-using-with
                stderr = open(self.project_path('stderr.txt'), 'w', encoding='utf-8')
            else:
                stdout = sys.stdout
                stderr = sys.stderr

            logger.info('Launching S2E')
            args, env = self._setup_env(options['project_args'], options['cores'], qmp_server)
            thr = S2EThread(args, env, self.project_path(), stdout, stderr)
            thr.start()

            while not s2e_main_process and not terminating():
                logger.info('Waiting for S2E to start...')
                time.sleep(1)

            if not no_tui:
                logger.info('Starting TUI')

                # We don't want the log messages to be sent to stdout when the
                # TUI is up. Ideally, we'd have a small window on the dashboard
                # to display logs in addition to writing them to a file.
                #
                # TODO: to put the console log into S2E last, we'll have to create s2e-out*
                # folders ourselves.
                log_file = self.project_path('log.txt')
                log_to_file(log_file)

                tui = Tui()
                tui.run(self.tui_cb)
            else:
                # If a timeout is provided, sleep for that amount. Otherwise
                # loop indefinitely
                _wait_for_termination(options['timeout'])

            logger.info('Terminating S2E')
            _terminate_s2e()
        finally:
            if qmp_server:
                qmp_server.shutdown()
                qmp_server.server_close()

        if s2e_main_process.returncode:
            raise CommandError(f'S2E terminated with error {s2e_main_process.returncode}')

    def _get_libs2e(self):
        with open(self.project_path('project.json'), 'r', encoding='utf-8') as fp:
            project_desc = json.loads(fp.read())

        qemu_build = self.image['qemu_build']
        qemu = self.install_path('bin', f'qemu-system-{qemu_build}')

        s2e_build = 's2e'
        if project_desc.get('single_path', False):
            s2e_build = 's2e_sp'

        return qemu, self.install_path('share', 'libs2e', f'libs2e-{qemu_build}-{s2e_build}.so')

    def _setup_env(self, project_args, cores, qmp_server):
        sn = qmp_server.socket.getsockname()
        server, port = sn[0], sn[1]

        qemu, libs2e = self._get_libs2e()

        env = os.environ.copy()
        env_s2e = {
            'S2E_MAX_PROCESSES': str(cores),
            'S2E_CONFIG': 's2e-config.lua',
            'S2E_UNBUFFERED_STREAM': '1',
            'S2E_SHARED_DIR': self.install_path('share', 'libs2e'),
            'LD_PRELOAD': libs2e,
            'S2E_QMP_SERVER': f'{server}:{port}'
        }
        env.update(env_s2e)

        args = [
            qemu,
            '-enable-kvm',
            '-drive',
            f'file={self.image["path"]},format=s2e,cache=writeback',
            '-serial', 'file:serial.txt',
            '-loadvm', self.image['snapshot'],
            '-monitor', 'null',
            '-m', self.image['memory'],
        ]

        graphics = env.get('GRAPHICS', '-nographic')
        if graphics:
            args.append(graphics)

        args = args + shlex.split(self.image['qemu_extra_flags']) + project_args

        return args, env

    def _get_data(self):
        elapsed_time = datetime.datetime.now() - self._start_time
        binaries = ', '.join(list(CollectorThreads.coverage.tb_coverage.keys()))
        if not binaries:
            binaries = 'Waiting for analysis to start...'

        gs = CollectorThreads.stats.global_stats
        cov = CollectorThreads.coverage.summary

        data = {
            'binaries': binaries,
            'run_time': elapsed_time,
            'core_count': f'{gs.get("instance_current_count", 0)}/{gs.get("instance_max_count", 0)}',
            'states': gs.get('state_highest_id', 0) - gs.get('state_completed_count', 0),
            'completed_states': gs.get('state_completed_count', 0),
            'completed_seeds': gs.get('seeds_completed', 0),
        }

        if self._cgc:
            data['covered_bbs'] = cov.get('covered_tbs_total', 0)
            data['num_crashes'] = CGCInterfacePlugin.crash_count
            data['pov1'] = CGCInterfacePlugin.pov1_count
            data['pov2'] = CGCInterfacePlugin.pov2_count
        else:
            data['num_crashes'] = gs.get('segfault_count', 0)

        return data

    def tui_cb(self, tui):
        data = self._get_data()
        tui.set_content(data, Command._legend, Command._layout)
        return not terminating()
