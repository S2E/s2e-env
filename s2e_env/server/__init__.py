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

import SocketServer
import socket
import json
import threading
import logging

from .cgc_interface import CGCInterfacePlugin
from .web_service_interface import WebServiceInterfacePlugin

logger = logging.getLogger(__name__)

PLUGINS = {
    'CGCInterface': CGCInterfacePlugin(),
    'WebServiceInterface': WebServiceInterfacePlugin()
}


class ThreadingMixIn2(object):
    """Mix-in class to handle each request in a new thread."""

    # Decides how threads will act upon termination of the
    # main process
    daemon_threads = False

    # Thread name prefix
    thread_name = "RequestHandlingThread-"

    def __init__(self):
        self.threads = []

    def process_request_thread(self, request, client_address):
        """Same as in BaseServer but as a thread.

        In addition, exception handling is done here.

        """
        try:
            self.finish_request(request, client_address)
            self.shutdown_request(request)
        except Exception:
            self.handle_error(request, client_address)
            self.shutdown_request(request)

    def process_request(self, request, client_address):
        """Start a new thread to process the request."""
        thread_name = self.thread_name + str(len(self.threads))
        logger.info('Starting thread "%s"', thread_name)
        t = threading.Thread(target=self.process_request_thread,
                             args=(request, client_address),
                             name=thread_name)
        t.daemon = self.daemon_threads
        t.start()
        self.threads.append(t)

    def wait_threads(self):
        logger.info('Waiting for unfinished threads')
        for t in self.threads:
            logger.info('Waiting for thread "%s"', t.name)
            try:
                t.join()
            except RuntimeError:
                # Failure happens when we join current thread or a not yet started thread
                pass


class QMPTCPServer(ThreadingMixIn2, SocketServer.TCPServer):
    allow_reuse_address = True
    timeout = 5
    queue = None

    def __init__(self, server_address, RequestHandlerClass):
        SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
        ThreadingMixIn2.__init__(self)
        self.stopped = False

    def shutdown(self):
        self.stopped = True
        SocketServer.TCPServer.shutdown(self)
        ThreadingMixIn2.wait_threads(self)


class LineRequestHandler(SocketServer.BaseRequestHandler):
    def __init__(self, *args, **kwargs):
        self.buf = ''
        self.sep = '\n'
        SocketServer.BaseRequestHandler.__init__(self, *args, **kwargs)

    def handle(self):
        self.request.settimeout(5)
        while not self.server.stopped:
            try:
                data = self.request.recv(1024)
            except socket.timeout as exception:
                if self.server.stopped:
                    break
                continue
            except socket.error as exception:
                logger.warning('Recv failed on socket: %s', str(exception))
                break

            self.buf += data
            while self.sep in self.buf:
                if self.server.stopped:
                    break
                line, self.buf = self.buf.split(self.sep, 1)
                self.callback(line)

        # Callback with None => connection closed
        self.callback(None)

        self.request.close()
        logger.debug('Socket closed.')

    def send(self, data):
        self.request.sendall(data)

    def flush(self):
        """ Empty the buffer, calling callback on content if required """
        if self.buf:
            self.callback(self.buf)
        self.buf = ''

    def callback(self, line):
        pass


class QMPConnectionHandler(LineRequestHandler):
    def __init__(self, *args, **kwargs):
        LineRequestHandler.__init__(self, *args, **kwargs)

    def callback(self, line):
        """What to do when QMP data comes"""
        if line is None:
            logger.debug('Connection closed')
            return

        try:
            obj = json.loads(line)
        except ValueError:
            logger.error('Invalid line received: %s', line)
            return

        if 'QMP' in obj:
            self.send('{ "execute": "qmp_capabilities" }\n')
            logger.debug("Sent handshake")
        else:
            analysis = self.server.analysis
            ret = self.handle_qmp(obj, analysis)
            if not ret:
                logger.info('Unhandled QMP request: %s', line)

    @staticmethod
    def handle_qmp(message, analysis):
        """Handle a QMP message.

        Returns:
        - True if the message was processed (no need to log directly)
        - False otherwise
        """

        if 's2e-event' not in message:
            return False

        processed = True
        data = message['s2e-event']

        for k in data.keys():
            if k in PLUGINS:
                plugin_processed = PLUGINS[k].process(data[k], analysis)
                if not plugin_processed:
                    processed = False
            else:
                processed = False

        return processed
