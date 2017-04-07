from argparse import ArgumentTypeError
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import socket
import stat
import sys
import tempfile
from threading import Event, Thread
import time
from zipfile import ZipFile

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import requests
import sh
from sh import ErrorReturnCode

from s2e_env import CONSTANTS
from s2e_env.command import EnvCommand, CommandError


#
# Argument parser checks
#

def _ram_type(value):
    """
    Ensure that the amount of RAM is sensible.
    """
    ivalue = int(value)

    if ivalue <= 0 or ivalue > 100 * 1024:
        raise ArgumentTypeError('The amount of image RAM must be less than '
                                '100 GB')
    return ivalue


def _cpu_cores_type(value):
    """
    Ensure that the number of CPU cores is sensible.
    """
    ivalue = int(value)

    if ivalue <= 0 or ivalue > 10:
        raise ArgumentTypeError('The number of cores must be between 1 and 10')
    return ivalue

#
# Snapshot helper functions
#

def _random_string(length=10):
    """
    Generate a random string of the given length.
    """
    import random
    import string

    return ''.join(random.choice(string.ascii_letters + string.digits) for
                   _ in range(length))


def _recv_qemu_msg(client, terminator='\x0d\x0a'):
    """
    Receive a message from QEMU.

    This message is transmitted over a socket.

    Args:
        client: Socket.
        terminator: String that determines the end of the message.

    Returns:
        The message.
    """
    msg = ''
    while True:
        msg += client.recv(256)
        if msg.endswith(terminator):
            break

    return msg[:-len(terminator)]


def _send_qemu_cmd(client, cmd):
    """
    Send a command to QEMU.

    This command is transmitted over a socket to a QEMU serial port. The
    supported commands are:

        * ``k <sometext>`` - Exits QEMU. Some combination of alphanumeric
                             characters is required in ``<sometext>``.
        * ``s <snapshot_name>``- Saves a snapshot named ``<snapshot_name>``.

    These are custom commands that have been added to QEMU's serial port code
    specifically for S2E (see
    https://github.com/S2E/qemu/blob/v1.0.50-se/hw/serial.c)

    Args:
        client: Socket.
        cmd: One of the commands described above.
    """
    time.sleep(0.5)

    for ch in '?!?MAGIC?!?%s ' % cmd:
        time.sleep(0.005)
        client.send(ch)


def _run_qemu(qemu, ev):
    """
    Run QEMU.

    Used as a thread target.

    Args:
        qemu: The QEMU command to run. Previously prepared by ``sh``.
        ev: Server ready event. QEMU will not run until the server indicates
            that it is ready.
    """
    ev.wait()
    qemu()


def _handle_qemu_boot(sock, ev):
    """
    Handles booting the QEMU virtual machine.

    The QEMU virtual machine is created to automatically run ``launch.sh``
    (https://github.com/S2E/guest-tools/blob/master/linux/scripts/launch.sh) at
    boot time. The first thing that this launch script does is write the kernel
    version to the serial port which is being tunnelled over a UNIX socket by
    QEMU.

    We therefore start listening on our UNIX socket, notify the QEMU thread
    that we are listening so that it can boot the virtual machine, and finally
    wait for QEMU to connect to our UNIX socket and send the kernel message to
    us.

    This function then returns a tuple containing:
        1. The client connect (so that we can communicate further with the VM
        2. The kernel version string
    """
    # Start listening and notify the QEMU thread that it can start the VM
    sock.listen(1)
    ev.set()

    client, _ = sock.accept()

    match = re.match(r"""^booted kernel (.*)""", _recv_qemu_msg(client))
    if not match:
        raise CommandError('Failed to read kernel version from QEMU virtual '
                           'machine')

    return client, match.group(1)


def _do_raw_boot(sock, ev):
    """
    Waits for a QEMU VM to boot and then sends the shutdown command.

    Used as a thread target.

    Why do we do this? Currently when an image is built the S2E kernel is not
    immediately available in GRUB (even after running grub-update, etc.). I'm
    not sure why this happens, but to solve it we can simply boot the image
    once and shut it down again. The next time that we boot the S2E kernel will
    be available in GRUB. Note that this assumes that the image is booted in
    "raw" format so that changes persist after shutdown.

    Once a better solution/the reason for this happening is found we can remove
    this code.

    Args:
        sock: The socket.
        ev: An event variable that is used to signal to the QEMU thread to
            start booting the QEMU image.
    """
    client = None
    try:
        # We don't care what kernel QEMU has booted into
        client, _ = _handle_qemu_boot(sock, ev)

        # Kill the VM
        _send_qemu_cmd(client, 'k kill')
    finally:
        # Clean up the connection
        if client:
            client.close()


def _do_snapshot(sock, snapshot_name, ev):
    """
    Waits for a QEMU VM to boot, takes a snapshot and then sends the shutdown
    command.

    Used as a thread target.

    Args:
        sock: The socket.
        snapshot_name: The name of the snapshot to produce.
        ev: An event variable that is used to signal to the QEMU thread to
            start booting the QEMU image.
    """
    client = None
    try:
        # Must boot into an S2E kernel
        client, kernel_version = _handle_qemu_boot(sock, ev)
        if 's2e' not in kernel_version:
            raise CommandError('Booted into kernel \'%s\'. Snapshots must be '
                               'taken when booted in an S2E kernel. Please '
                               'fix your image to boot into an S2E kernel' %
                               kernel_version)

        # Take the snapshot
        _send_qemu_cmd(client, 's %s' % snapshot_name)
    finally:
        # Clean up the connection
        if client:
            client.close()


class Command(EnvCommand):
    """
    Builds an image.

    This involves:
        * Building a QEMU raw image based on a Packer (https://packer.io)
          template
        * Creating a JSON description of the image
        * Booting the image once in "raw" mode to ensure that the S2E kernel
          is registered with GRUB
        * Booting the image again in "s2e" mode to take a snapshot
    """

    help = 'Build an image.'

    def __init__(self):
        super(Command, self).__init__()

        # If we are running without an X session, run QEMU in headless mode
        self._headless = os.environ.get('DISPLAY') is None

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('template',
                            help='The name of a Packer JSON template to build '
                                 'the image from. Available templates can be '
                                 'listed with the ``s2e image_templates`` '
                                 'command')
        parser.add_argument('-n', '--name', required=False, default=None,
                            help='Name of the created image file. Defaults to '
                                 'the name given in the Packer template file')
        parser.add_argument('-d', '--headless', action='store_true',
                            help='Build the image in headless mode (i.e. '
                                 'without a GUI)')
        parser.add_argument('-s', '--snapshot', required=False,
                            default='ready', help='Snapshot name. Defaults to '
                                                  '\'ready\'')
        parser.add_argument('-m', '--memory', required=False, default=256,
                            type=_ram_type,
                            help='Amount of RAM allocated to the image. '
                                 'Defaults to 256 MB')
        parser.add_argument('-c', '--num-cores', required=False, default=4,
                            type=_cpu_cores_type,
                            help='The number of cores used when building the '
                                 'QEMU virtual machine image. Defaults to 4')

    def handle(self, **options):
        template = options['template']
        snapshot = options['snapshot']
        memory = options['memory']
        image_name = options['name']
        num_cores = options['num_cores']

        # Only override the system settings if specified
        if options['headless']:
            self._headless = True

        # Check that S2E guest tools have been built
        if not glob.glob(self.env_path('bin', 'guest-tools*')):
            raise CommandError('Guest tools could not be located in %s. Have '
                                'you run ``s2e build``?' %
                                self.env_path('bin'))

        # Look for the template file among the available image source
        # directories and parse it
        template_path, template_json = self._find_template_and_parse(template)
        template_name, _ = os.path.splitext(os.path.basename(template_path))
        template_dir = os.path.dirname(template_path)

        # Exit if we could not find the image template
        if template_json is None:
            raise CommandError('%s it not a valid image template. Valid '
                               'images can be listed with '
                               '``s2e image_templates``' % template_name)

        # Run packer build
        self._packer_build(template_dir, template_name, snapshot, num_cores)

        # Check for the Packer manifest file
        manifest_path = os.path.join(template_dir, 'packer-manifest.json')
        if not os.path.isfile(manifest_path):
            raise CommandError('Packer did not create a manifest file. Was '
                               'the build successful?')

        # Parse the Packer manifest file (it is just JSON)
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        # Based on the information in the manifest file, move the image into
        # the images directory, add the .s2e extension and create a JSON
        # description of the image
        for build in manifest.get('builds', []):
            build_name = build['name']

            # Check the files listed in the build. Only one file should have
            # been created. If multiple files have been created, we only take
            # the first file. Who knows what will happen if we do this, so warn
            # the user
            build_files = build.get('files', [])
            if len(build_files) == 0:
                raise CommandError('Building template %s did not create any '
                                   'files' % template_name)
            elif len(build_files) != 1:
                self.warn('Building from %s created multiple output files. '
                          'Something weird may have happened' % template_name)

            build_file_path = os.path.join(template_dir,
                                           build_files[0]['name'])
            build_file_size = build_files[0]['size'] / 1024 / 1024

            # Move the image into the images directory. If the user specified
            # a name for the image file, use it
            if not image_name:
                image_name = build_name

            s2e_img_path = self.env_path('images', '%s.raw.s2e' % image_name)
            image_desc_path = self.env_path('images', '.%s.json' % image_name)

            shutil.move(build_file_path, s2e_img_path)
            self.info('Moved image from %s to %s' % (build_file_path,
                                                     s2e_img_path))

            # Find the correct builder in the Packer template file that
            # corresponds to this manifest build
            builder = None
            for builder in template_json['builders']:
                if builder['name'] == build_name:
                    break

            if builder is None:
                raise CommandError('Could not find the Packer builder for the '
                                   '%s build' % build_name)

            qemu_exe_name = builder['qemu_binary']

            # Snapshot the image
            self._take_snapshot(qemu_exe_name, s2e_img_path, memory, snapshot)

            # Save a JSON description of the image
            creation_time = time.mktime(datetime.datetime.now().timetuple())
            image_desc = {
                'path': s2e_img_path,
                'template': template_path,
                'creation_time': creation_time,
                'qemu': qemu_exe_name,
                'size': build_file_size,
                'memory': memory,
                'md5': hashlib.md5(open(s2e_img_path).read()).hexdigest(),
                'snapshot': snapshot,
            }

            with open(image_desc_path, 'w') as f:
                json.dump(image_desc, f)

            self.info('Created JSON description %s.json' % build_name)

        # Clean up the Packer build directory
        self._packer_cleanup(template_dir)

        return 'Built image \'%s\' from template \'%s\'' % (image_name,
                                                            template_name)

    #
    # Packer methods
    #

    def _find_template_and_parse(self, template):
        """
        Find the image's JSON template file and parse it.

        Args:
            template: Either the name of or a path to an image template file.

        Returns:
            A tuple containing:
                1. The path to the template file.
                2. The parsed JSON template as a ``dict``.
        """
        template_json = None
        for img_repo in CONSTANTS['repos']['images'].values():
            img_src_dir = self.env_path('source', img_repo)

            # Construct the path to the Packer template file. The user can
            # specify either a path or the name of an image from the
            # `image_templates` command
            if os.sep in template:
                template_path = os.path.realpath(template)
            else:
                template_path = os.path.join(img_src_dir, template)

            if not template_path.endswith('.json'):
                template_path = '%s.json' % template_path

            # Try to load the Packer template file. If this fails, keep looking
            try:
                with open(template_path, 'r') as f:
                    template_json = json.load(f)
                break
            except Exception:
                pass

        return template_path, template_json

    def _get_packer(self):
        """
        Create the packer command.

        If the packer binary does not exist, download it.
        """
        packer_path = self.env_path('bin', 'packer')
        if not os.path.isfile(packer_path):
            self._download_packer()

        return sh.Command(packer_path)

    def _download_packer(self):
        """
        Download Packer.

        Packer is the tool used to build S2E images. It is downloaded as a zip
        file which is then unzipped into the project's bin directory.
        """
        self.info('Fetching Packer')

        packer_url = CONSTANTS['packer']['url']
        response = requests.get(packer_url)

        if response.status_code != 200:
            raise CommandError('Unable to download Packer from %s' %
                               packer_url)

        packer_zip = ZipFile(StringIO(response.content))
        try:
            packer_zip.getinfo('packer')
        except KeyError:
            raise CommandError('The downloaded file does not contain the '
                               'packer binary')
        packer_zip.extract('packer', self.env_path('bin'))
        packer_zip.close()
        self.success('Fetched Packer')

        # Ensure that the packer binary is executable
        packer_path = self.env_path('bin', 'packer')
        st = os.stat(packer_path)
        os.chmod(packer_path, st.st_mode | stat.S_IEXEC)

    def _packer_build(self, template_dir, template_name, snapshot='ready',
                      num_cores=4):
        """
        Runs ``packer build`` on the given template file to create the image.
        """
        # Get the packer executable
        packer = self._get_packer()

        # Change into the template directory
        orig_dir = os.getcwd()
        os.chdir(template_dir)

        # Run packer to create the image. This will create an image and a
        # manifest file
        try:
            self.info('Building image from %s' %
                      os.path.join(template_name, template_dir))
            s2e_install = self.env_path('bin')
            packer.build('-var', 's2e_install=%s' % s2e_install,
                         '-var', 'snapshot_name=%s' % snapshot,
                         '-var', 'headless=%s' % str(self._headless).lower(),
                         '-var', 'cores=%d' % num_cores,
                         '-force', '%s.json' % template_name,
                         _out=sys.stdout, _err=sys.stderr, _fg=True)
            self.success('Image %s built' % template_name)
        except ErrorReturnCode as e:
            raise CommandError(e)
        finally:
            # Change back to the original directory
            os.chdir(orig_dir)

    def _packer_cleanup(self, template_dir):
        """
        Cleanup previous Packer builds.
        """
        self.info('Cleaning up previous Packer builds')

        # Check for a manifest file. If it does not exist, our work is done
        manifest_path = os.path.join(template_dir, 'packer-manifest.json')
        if not os.path.isfile(manifest_path):
            return

        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        # Remove each output directory listed in the manifest. Each output
        # directory will be relative to the source directory
        for build in manifest.get('builds', []):
            for file_ in build.get('files', []):
                output_dir = os.path.join(template_dir,
                                          os.path.dirname(file_['name']))
                shutil.rmtree(output_dir)

        # Finally delete the manifest file
        os.remove(manifest_path)

    #
    # Snapshot methods
    #

    def _take_snapshot(self, qemu_exe_name, img_path, memory, snapshot_name):
        """
        Take a snapshot of the given image with the given amount of RAM.

        Args:
            qemu_exe_name: Name of the QEMU executable. Must be in the format
                           ``qemu-system-<arch>``, where ``<arch>`` is i386,
                           x86_64, etc.
            img_path: Path to the QEMU image.
            memory: Amount of memory to run QEMU with. This must be consistent
                    with what we write in the image's JSON description file,
                    because when we resume the snapshot QEMU must be started
                    with the same amount of memory.
            snapshot_name: The name of the snapshot.
        """
        # Generate a random file to use for the socket
        gen_sock_path = lambda: os.path.join(tempfile.gettempdir(),
                                             's2e-sock-%s' % _random_string())
        sock_file = gen_sock_path()
        while os.path.exists(sock_file):
            sock_file = gen_sock_path()

        # Create the QEMU command.
        #
        # By this point we have already checked that S2E has been built, so
        # don't bother checking that this path exists
        qemu_path = self.env_path('bin', qemu_exe_name)
        qemu_ = lambda drv_fmt: \
            sh.Command(qemu_path).bake('-drive',
                                       'file=%s,format=%s,cache=writeback' %
                                            (img_path, drv_fmt),
                                       '-k', 'en-us', '-enable-kvm',
                                       '-m', memory, '-net', 'none',
                                       '-net', 'nic,model=e1000',
                                       '-chardev',
                                       'socket,path=%s,id=s2e-sock' %
                                            sock_file,
                                       '-serial', 'chardev:s2e-sock',
                                       '-enable-serial-commands',
                                       _out=sys.stdout, _err=sys.stderr,
                                       _fg=True)
        if self._headless:
            qemu = lambda drv_fmt: \
                qemu_(drv_fmt).bake('-nographic', '-monitor', 'null')
        else:
            qemu = qemu_

        # Find libs2e
        #
        # Get the architecture from the QEMU executable name. QEMU executable's
        # are named qemu-system-<arch>, where <arch> is i386, x86_64, etc.
        arch = qemu_exe_name.split('-')[-1]
        libs2e_path = self.env_path('share', 'libs2e', 'libs2e-%s.so' % arch)
        if not os.path.isfile(libs2e_path):
            raise CommandError('No libs2e at %s' % libs2e_path)

        # Create the libs2e environment variable for taking the snapshot
        env_vars = os.environ.copy()
        env_vars['LD_PRELOAD'] = libs2e_path

        try:
            # Create the UNIX socket
            self.info('Creating UNIX socket at %s to communicate with QEMU' %
                      sock_file)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(sock_file)

            # Do the initial raw boot/shutdown to make the S2E kernel available
            # in GRUB
            self._run_threads(_do_raw_boot, (sock,),
                              (qemu('raw'),),
                              msg='Making S2E kernel available')

            # Take the snapshot
            self._run_threads(_do_snapshot, (sock, snapshot_name),
                              (qemu('s2e').bake(_env=env_vars),),
                              msg='Taking snapshot')
        finally:
            os.unlink(sock_file)

    def _run_threads(self, ctrl_target, ctrl_args, qemu_args, msg=None):
        """
        Run the QEMU socket threads.

        Two threads are run - a "control" thread and a "QEMU" thread.

        Control thread
        --------------

        The control thread essentially acts as a server - it starts the UNIX
        socket and listens for a client (in this case, QEMU) to connect and
        send the kernel version (see the ``_handle_qemu_boot`` function for
        details).

        QEMU thread
        -----------

        The QEMU thread waits for the control thread to signal that it is ready
        for QEMU to boot, then it boots the QEMU image and tunnels the image's
        serial port (/dev/ttyS0) over the UNIX socket to communicate with the
        control thread.

        Args:
            ctrl_target: Function that the control thread will run.
            ctrl_args: A tuple of arguments to the ``ctrl_target`` function.
            qemu_args: A tuple of arguments to the QEMU thread's target (always
                       ``_run_qemu``).
            msg: An optional message to display to the user.
        """
        if msg:
            self.info(msg)

        # Create the threads and their synchronization primative
        event = Event()
        qemu_thread = Thread(target=_run_qemu, args=qemu_args + (event,))
        control_thread = Thread(target=ctrl_target, args=ctrl_args + (event,))

        qemu_thread.daemon = True
        control_thread.daemon = True

        # Start the threads
        qemu_thread.start()
        control_thread.start()

        # Wait for the threads to complete
        qemu_thread.join()
        control_thread.join()
