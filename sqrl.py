#!/usr/bin/python
# -*- coding: utf-8 -*-

# TODO: read_config to check config for validity

""" the main application of sqrl the bot """

from sqrl3.constants import GreenletRehash, ConfigMalformed, ConfigDoesNotExist, IN, OUT, OTHER, IN_PRIVMSG, IN_ACTION, IN_NOTICE, OUT_PRIVMSG, OUT_ACTION, OUT_NOTICE
from sqrl3.utils import mask_to_string, string_to_mask, color
import os, sys

SQRLNAME = "sqrl3"
SQRLVERSION = 0.3

group = None

def main():
    global group

    ########################################################################### import stuff

    import platform, argparse, logging
    try:
        from gevent.pool import Group
        from gevent import signal
    except ImportError:
        print "this application requires gevent\n"
        raise
    from sqrl3 import conf, irc, script

    def description(author="sqrrl"):
        return u"%s version %s by %s\nrunning on python %s.%s, %s %s" % \
            (SQRLNAME, SQRLVERSION, author, sys.version_info[0], sys.version_info[1], platform.system(), platform.release())

    ########################################################################### parse arguments

    parser = argparse.ArgumentParser(description=description(), prog="sqrl")
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + str(SQRLVERSION))
    parser.add_argument('-c', '--config', action='store', dest='config_file', default=conf.FILE,
                        metavar='file', help='use the specified JSON config file')
    parser.add_argument('-fds', '--file-descriptors', metavar='fd:tag:mask', action='store', nargs="+",
                        help='open file descriptors for reuse')
    args = parser.parse_args()

    # parsing done, print greeting
    print description(), "\n"

    ########################################################################### try loading the config

    config_file = args.config_file
    try:
        conf.read(config_file)
    except ConfigDoesNotExist:
        print u"it appears that the confing file “%s” does not exist yet.\ni will create this config file right now, please edit it and restart the application." % config_file
        try:
            conf._config = conf.DEFAULT
            conf.write(config_file)
        except IOError as e:
            print u"error while writing config file “%s”: I/O error %s" % (config_file, e)
            sys.exit(1)
        else:
            sys.exit(0)
    except IOError as e:
        print u"error while reading config file “%s”: I/O error %s" % (config_file, e)
        sys.exit(1)
    except ConfigMalformed:
        print u"error: config file “%s” is malformed" % config_file
        sys.exit(1)

    ########################################################################### set up logging

    logging.basicConfig(format="%(asctime)s %(name)5.5s %(levelname)s | %(message)s", datefmt='%m-%d %H:%M')
    logging.addLevelName(IN, color("<-", 3))
    logging.addLevelName(IN_PRIVMSG, color("<=", 3))
    logging.addLevelName(IN_NOTICE, color(u"<≡", 3))
    logging.addLevelName(IN_ACTION, color("<*", 3))
    logging.addLevelName(OUT, color("->", 6))
    logging.addLevelName(OUT_PRIVMSG, color("=>", 6))
    logging.addLevelName(OUT_NOTICE, color(u"≡>", 6))
    logging.addLevelName(OUT_ACTION, color("*>", 6))
    logging.addLevelName(logging.ERROR, color("ER", 1))
    logging.addLevelName(OTHER, color("--", 2))

    ########################################################################### catch SIGINT / SIGQUIT / SIGTERM

    signal(1, rehash_safe, "SIGHUP")
    signal(2, shutdown, "SIGINT")   # doesn't work in gevent 0.3.8
    signal(3, shutdown, "SIGQUIT")
    signal(15, shutdown, "SIGTERM")

    ########################################################################### get file descriptors

    fds, mes = {}, {}
    if args.file_descriptors:
        for fd in args.file_descriptors:
            fd, tag, mask = fd.split(":", 2)
            fds[tag] = int(fd)
            mes[tag] = string_to_mask(mask)

    ########################################################################### spawn the greenlets

    class Irc(script.Scripto, irc.Irc):
        pass

    group = Group()
    for tag in conf.getconnections():
        if tag != "default":
            group.start(Irc(tag, fds.get(tag, None), mes.get(tag, None)))
    group.join()

    ########################################################################### this should get displayed

    print "\ngood-bye!\n"

###############################################################################
###############################################################################
###############################################################################

def shutdown(reason="?"):
    """
        to be called by control scripts & SIGTERM / SIGQUIT / SIGINT
        shutdown() must be non-blocking lest group.greenlest gets edited during iteration
    """
    print "\nshutting down (%s)\n" % reason
    for greenlet in group.greenlets:
        greenlet.shutdown()


def rehash(reason="?"):
    """
        to be called from control scripts & SIGHUP
        restart the bot without disconnecting from IRC
    """
    def destroyer():
        """
            the last running greenlet
            1. prepare arguments for new executable
            2. kill all greenlets but oneself by calling shutdown(GreenletRehash),
                which kills them, yet does not disconnect from IRC
            3. register lastfunc to be run on system exit
            4. die naturally
        """
        argv = [sys.executable, "-m", SQRLNAME]
        try:
            argv += sys.argv[1:sys.argv.index("--file-descriptors") + 1]
        except ValueError:
            argv += sys.argv[1:] + ["--file-descriptors"]
        # for each greenlet:
        # * get socket fileno, tag, mask
        # * raise GreenletRehash in greenlet and its group
        # those greenlets of the group which catch GreenletRehash will see SystemExit
        # other greenlets will see it as GreenletExit and will get killed naturally
        for greenlet in group.greenlets:
            if greenlet.connected:
                argv.append(":".join((str(greenlet.net.sock.fileno()), greenlet.tag, mask_to_string(greenlet.me))))
            greenlet.shutdown(GreenletRehash)
        # os.execv is scheduled to run last
        # since atexit runs stuff in LIFO manner,
        # we create a function that replaces it
        exitfunc = sys.exitfunc
        def lastfunc():
            try:
                exitfunc()
            finally:
                os.execv(sys.executable, argv)
        # after registering this function, die naturally
        # this greenlet should be the last one, and
        # as the main greenet dies, all the atexit functions and
        # the replacer function will be run in this order
        sys.exitfunc = lastfunc

    # try to compile all the files
    # if can't compile them all, raise SyntaxError and don't rehash
    from compileall import compile_dir
    from gevent import spawn
    if compile_dir(os.path.dirname(__file__), quiet=True) == 0:
        if reason == "SIGHUP":
            print "\ncould not compile files\n"
            return
        else:
            raise SyntaxError
    # files can be compiled, spawn destroyer and return
    # we spawn another greenlet because the current one is going to be
    # destroyed and won't be able to continue to os.execv
    print "\nrehashing (%s)\n" % reason
    spawn(destroyer)

def rehash_safe(reason="?"):
    """
        calls rehash;
        doesn't raise anything
    """
    try:
        rehash(reason)
    except Exception as e:
        print e
