#!/usr/bin/python
# -*- coding: utf-8 -*-

""" provides plugins """

import conf
from gevent import GreenletExit
from utils import ischannel, get_args, first_line
from irc import Irc, Privmsg, Notice, Action, TextMessage, Message, Numeric
from constants import MuteMessage, HaltMessage, OTHER, BotException
import inspect
import sys
from functools import wraps, partial
from importlib import import_module
from collections import namedtuple

g_scripts = {}
g_meta = {}

Meta = namedtuple("Meta", ["name", "doc", "commands"])

######################################################################
######################################################################
######################################################################

class Scripto(object):
    def __init__(self, *args, **kwargs):
        super(Scripto, self).__init__(*args, **kwargs)
        self.handlers = {}
        self.meta = {}
        # make a list of scripts used on this network
        scripts = set(conf.get("scripts", tag=self.tag))
        for chan in self.chans:
            scripts.update(conf.get("scripts", tag=self.tag, chan=chan))
        # load them as needed
        self.logger.log(OTHER, "imported: [%s]" % ", ".join(
            [name for name in scripts if self._loadscript(name) == 2]
        ))

    ################################################################## S P A W N

    def spawn(self, func, *args, **kwargs):
        """
            launch a function as a gevent thread
            it's launched inside a try/else closure
            well, that's useful for printing exception, but not much otherwise
        """
        def protected():
            try: func(*args, **kwargs)
            except GreenletExit: return
            except Exception as e: self.onexception(e, unexpected=True)
        self.group.spawn(protected)

    ################################################################## L O A D / U N L O A D

    def _loadscript(self, name):
        """
            imports module and append it to global list or channel list
            doesn't raise anything
            returns:
                0 if module could not be loaded
                1 if it was loaded, but no import was necessary
                2 if it was loaded, but import was necessary
        """
        if name in g_scripts:
            return 1
        else:
            try:
                module = import_module("sqrl3.scripts." + name)
            except Exception as e:
                self.onexception("error while importing '%s': %s" % (name, e), unexpected=True)
                return 0
            handlers = {}
            defcommands = {}
            for _, func in inspect.getmembers(module, inspect.isfunction):
                if hasattr(func, "mtype"):
                    if func.commands:
                        # for @onprivmsg("title, "ti"):
                        # g_scripts["title"] += {"title": func, "ti": func}
                        # g_meta["title"] += Meta("title", "my cute module", {"title": "my cute title"})
                        defcommands[func.commands[0]] = None if func.__doc__ is None else first_line(func.__doc__)
                        for command in func.commands:
                            assert command not in handlers, "cannot define the same command twice"
                            handlers[command] = func
                    else:
                        # for @onprivmsg:
                        # g_scripts["title"] += {Privmsg: func}
                        assert func.mtype not in handlers, "cannot have more than one handler for the same message type"
                        handlers[func.mtype] = func
                elif hasattr(func, "ttype"):
                    # for @onload:
                    # g_scripts["title"] += {irc.Irc.onload: func}
                    assert func.ttype not in handlers, "really, what are you doing?"
                    handlers[func.ttype] = func
            g_scripts[name] = handlers
            g_meta[name] = Meta(name=name, doc=None if module.__doc__ is None else first_line(module.__doc__), commands=defcommands)
            return 2

    def loadscript(self, name, chan=None):
        """
            import and load a script by name,
            adjustings config if necessary for given channel or network
            returns 0, 1, 2 as _loadscript
        """
        status = self._loadscript(name)
        if status:
            if name not in conf.get("scripts", self.tag, chan):
                conf.append("scripts", name, self.tag, chan)
        if status:
            try: func = g_scripts[name][Irc.onload]
            except KeyError: pass
            else: self._runtrigger(func)
        return status

    def unloadscript(self, name, chan=None):
        """
            unload script (does not remove it from memory) by name
            adjustings config if necessary for given channel or network
            returns 1 if removed and 2 if it wasn't loaded
        """
        if name in conf.get("scripts", self.tag, chan):
            try: func = g_scripts[name][Irc.onunload]
            except KeyError: pass
            else: self._runtrigger(func)
            conf.remove("scripts", name, self.tag, chan)
            return 1
        return 0

    def reloadscript(self, name):
        """
            relad script
            THIS IS A HACK! YOU DON'T RELOAD MODULES IN PYTHON! USE ONLY FOR TESTING PURPOSES!
            returns 2 on success, raises on fail
        """
        del g_scripts[name], g_meta[name]
        reload(sys.modules["sqrl3.scripts." + name])
        return self._loadscript(name)

    ################################################################## S U B C L A S S I N G

    def onmessage(self, msg):
        Irc.onmessage(self, msg)
        # chan = message's channel or None
        chan = getattr(msg, "target", None)
        if chan and not ischannel(chan):
            chan = None
        # get a list of handlers
        handlers = list(self._get_handlers(chan))
        iscommand = lambda word: any(word in handler for handler in handlers)
        # command = "title" for Privmsgs with "♥title" / "bot: title" / pm "title"
        # command = 123 for Numerics
        command = None
        if type(msg) is Privmsg and len(msg):
            first = msg[0]
            if msg.tomyself:
                if iscommand(first):
                    # "cmd hello" in private
                    command = msg.command = first
                    msg.splitmsg = msg.splitmsg[1:]
            elif first[0] == conf.get("prefix", tag=self.tag, chan=chan):
                if iscommand(first[1:]):
                    # "♥cmd hello" in #chan
                    command = msg.command = first[1:]
                    msg.splitmsg = msg.splitmsg[1:]
            elif len(msg) > 1 and first[:-1] == self.me[0] and first[-1] in (",", ":"):
                if iscommand(msg[1]):
                    # "bot: hello" in #chan
                    command = msg.command = msg[1]
                    msg.splitmsg = msg.splitmsg[2:]
        elif type(msg) is Numeric:
            command = msg.num
        try:
            for handler in handlers:
                for mtype in reversed(msg.__class__.__mro__[:-1]):
                    # for each script, and then for each message type, do:
                    # @onprivmsg / @onnotice
                    if mtype in handler:
                        self._onmessage(handler[mtype], msg, chan=None)
                # for each script, do:
                # @onprivmsg("title") / @onnumeric(123)
                if command and command in handler:
                    self._onmessage(handler[command], msg, chan)
        except HaltMessage:
            return

    def _onmessage(self, func, msg, chan):
        """
            a helper function for onmessage, catches exceptions
            if func.block is True, execute it immediately
            if func.kingly is True, run function only if it's from master
        """
        def protected():
            try: func(self, msg)
            except GreenletExit: return                             # if the function returned GreenletExit, return
            except HaltMessage: raise                               # if it's a HaltMessage, raise so that onmessage can catch it. note that if block=False, this has no effect
            except MuteMessage:                                     # if it's a MuteMessage, destoy msg's reply/ireply/action
                self.logger.log(OTHER, "muting message")
                msg.mute()
            except Exception as e:                                  # if it's an unexpected exception, print "Exception: data". if onex==False, no effect
                self.onexception(e, unexpected=not isinstance(e, BotException))
                if func.onex is not False:
                    if func.onex is True: msg.action("failed with {0.__class__.__name__}: {0}", e)
                    else: msg.action(func.onex, e)
        if func.kingly is not False and not msg.frommaster:         # if a kingly command is called by a peasant, print bewilderment. if kingly=="", no effect
            if func.kingly is True: msg.reply("who do you think you are?")
            elif func.kingly != "": msg.reply(func.kingly)
            return
        if func.block:                                              # if function is not blocking, it will be run after all the scheduling, else right now
            protected()
        else:
            self.group.spawn(protected)

    ##################################################################

    def onload(self, *args, **kwargs):
        self._ontrigger(Irc.onload, args, kwargs)

    def onunload(self, *args, **kwargs):
        self._ontrigger(Irc.onunload, args, kwargs)

    def onconnected(self, *args, **kwargs):
        self._ontrigger(Irc.onconnected, args, kwargs)

    def ondisconnect(self, *args, **kwargs):
        self._ontrigger(Irc.ondisconnect, args, kwargs)

    def _ontrigger(self, ttype, args, kwargs):
        """
            a helper function for onload / ounload / etc
            also magically runs the function these subclass
        """
        ttype(self, *args, **kwargs)
        for handler in self._get_handlers(None):
            try: func = handler[ttype]
            except KeyError: continue
            self._runtrigger(func, *args, **kwargs)

    def _runtrigger(self, func, *args, **kwargs):
        try: func(self, *args, **kwargs)
        except Exception as e: self.onexception(e, unexpected=True)

    ##################################################################

    def _get_handlers(self, chan):
        """
            yield handlers for channel in form:
                {Privmsg: f1, "title": f2, onload: f3}, {...}
            if chan is None, return handlers for network
        """
        for name in conf.get("scripts", self.tag, chan):
            if name in g_scripts:
                yield g_scripts[name]

######################################################################
###################################################################### D E C O R A T O R S
######################################################################

def command(mtype, *commands, **settings):
    """
        wrapper around commands
        retrieves settings for arguments and keyword arguments beyond net, msg
        special keyword arguments:
            block=False: execute immediately (non-threadedly).
                can be True or False
            kingly=False: execute only if sender is master. send error reply when sender is not.
                can be False (not kingly), True (default reply), "string" (send this) or "" (don't send anything)
            onex: send error reply when unexpected exception happened.
                =True for Privmsgs with commands and =False with messages without them
                can be False (don't send), True (default reply), "string" (send this, is formatted with one positional argument - the exception)
    """
    def irc_handler(func):
        f = construct_wrapper(Irc.onmessage, func)                  # all source functions have the same arguments
        f.mtype, f.block, f.kingly = mtype, settings.get("block", False), settings.get("kingly", False)
        f.commands = commands if commands else None
        f.onex = settings.get("onex", True) if mtype is Privmsg and commands else False
        return f
    if len(commands) == 1 and inspect.isfunction(commands[0]):      # if the wrapper was written as @onprivmsg
        func, commands = commands[0], None
        return irc_handler(func)
    else:                                                           # if it was written as @onprivmsg() / @onprivmsg("...", ...)
        return irc_handler

onprivmsg = partial(command, Privmsg)
onnotice = partial(command, Notice)
onaction = partial(command, Action)
ontextmessage = partial(command, TextMessage)
onmessage = partial(command, Message)
onnumeric = partial(command, Numeric)

######################################################################

def trigger(ttype):
    """
        wrapper for triggers such as onload / onunload / onconnected / etc
        retreives setting for arguments and keywords beyond those of source function
    """
    def trigger_handler(func):
        f = construct_wrapper(ttype, func)
        f.ttype = ttype
        return f
    return trigger_handler

onload = trigger(Irc.onload)
onunload = trigger(Irc.onunload)
onconnected = trigger(Irc.onconnected)
ondisconnect = trigger(Irc.ondisconnect)

######################################################################

def construct_wrapper(sfunc, tfunc):
    targs, tkwargs, tdefs = get_args(tfunc)
    sargs, _, _ = get_args(sfunc)
    assert len(targs) >= len(sargs), "%s has not enough arguments" % tfunc
    targs = targs[len(sargs):]
    if not targs and not tkwargs:
        return tfunc
    else:
        nms = dict(get=conf.get, getd=conf.getdefault, tfunc=tfunc, **{"_%s" % i: de for i, de in (enumerate(tdefs) if tdefs else [])})
        code = "def wrapper({sargs}, chan=None):\n" \
               " tag = self.tag\n" \
               " tfunc({sargs}{targs}{tkwargs})".format(
                   sargs=", ".join(sargs),
                   targs="".join(", get('%s', tag, chan)" % arg for arg in targs),
                   tkwargs="".join(", getd('%s', tag, chan, default=_%s)" % (arg, i) for i, arg in enumerate(tkwargs)) if tkwargs else "")
        exec code in nms
        return wraps(tfunc)(nms["wrapper"])
