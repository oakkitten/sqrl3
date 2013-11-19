#!/usr/bin/python
# -*- coding: utf-8 -*-

# TODO: ssl

""" primitive gevent TCP interface """

import gevent
from gevent import socket, sleep
from gevent.queue import Queue
from constants import ConnectionFailed, ConnectionTimeout, ConnectionTerminated


class Network(object):
    """
        primitive gevent TCP inferface.
        raises ConnectionFailed, ConnectionTimeout, ConnectionTerminated
        if fd is present, this gets reconnected to that fd
    """

    def __init__(self, fd=None, timeout=200, readbuffer=4096, sendinterval=1.0):
        self.timeout = timeout
        self.readbuffer = readbuffer
        self.sendinterval = sendinterval
        self.sendertasklet = None
        if fd is not None:
            self.reconnect(fd)

    def connect(self, address, ssl=False, source_address=None):
        """ connect to address/port """
        assert self.sendertasklet is None
        try:
            self.sock = socket.create_connection(address, self.timeout, source_address)
        except socket.timeout as e:
            raise ConnectionTimeout(e)
        except Exception as e:
            raise ConnectionFailed(u"Could not connect: %s" % e)
        self._prepare()

    def reconnect(self, fd):
        """ connect to an already connected socket """
        assert self.sendertasklet is None
        self.sock = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self._prepare()

    def _prepare(self):
        # this overcomes gevent 1.0 lack of link_exception
        def patricider():
            try: self.sender()
            except Exception as e: parent.kill(e)
        parent = gevent.getcurrent()
        self.sendertasklet = gevent.spawn(patricider)
        self.data, self.queue = "", Queue()

    def disconnect(self):
        """
            shutdown, close the socket and delete it.
            should not raise anything if called after connect()
        """
        self.sendertasklet.kill()
        self.sendertasklet = None
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except socket.error:    # any socket error, probably errno.ENOTCONN
            pass                # discard them all, although maybe we shouldn't do that
        self.sock.close()
        del self.data, self.queue

    def sender(self):
        while True:
            data = self.queue.get()
            try:
                self.sock.send(data, timeout=self.timeout)
            except socket.timeout as e:
                raise ConnectionTimeout(e)
            except Exception as e:
                raise ConnectionFailed(u"Could not send: %s" % e)
            sleep(self.sendinterval)

    def send(self, data):
        """
            sends data, obeying interval
            returns immediately
        """
        self.queue.put(data)

    def getline(self):
        """
            return lines until there are no lines to return.
            raises ConnectionTerminated when done
        """
        while True:
            try:
                out, self.data = self.data.split("\r\n", 1)
            except ValueError:
                try:
                    new = self.sock.recv(self.readbuffer)
                except Exception as e:
                    raise ConnectionFailed(u"Could not receive: %s" % e)
                if not new:
                    raise ConnectionTerminated(u"Server closed the connection")
                self.data += new
            else:
                return out
