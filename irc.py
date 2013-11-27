#!/usr/bin/python
# -*- coding: utf-8 -*-

""" provides irc connection abstraction """

# TODO: quit loop if too many exception raised during a short period of time

from gevent import Greenlet, sleep, GreenletExit
from gevent.pool import Group
from network import Network
from constants import GreenletRehash, ConnectionFailed, MessageMalformed, IN, OUT, OTHER, IN_PRIVMSG, IN_ACTION, OUT_PRIVMSG, OUT_ACTION, OUT_NOTICE
from utils import CuteFormatter, string_to_mask, mask_to_string
import re
import conf
import logging
from copy import copy

###################################################################################################
################################################################################################### connection
###################################################################################################

class Irc(Greenlet):
    """
        irc connection abstraction. inherits:
        start(), join(), kill(exception=GreenletExit, block=False, timeout=None), ready(), successful(), etc
        __init__ only receives:
            tag:        "myfreenode",
            fd:         2 or None

        the other options are accessed through the following properties,
        which delegate calls to conf.get:
            servers:    [Server("server.address +1234"), ...],
            encoding:   "utf-8"
            network:    "freenode",
            nick:       "sqrl",
            username:   "sqrl",
            password:   "server password",
            nickservpassword: "nisckerv password",
            realname:   "real name",
            chans:      ["#channel": {"blacklist": ["ex"]}, ...],
            scripts:    ["users", "seen", "com", "version", "wik", "title", "choice", "dic", "ex", ...],
            masters:    ["*!*@unaffiliated/squirrel", ...]
    """

    def __init__(self, tag, fd=None, me=None):
        super(Irc, self).__init__()
        self.tag = tag
        self.net = Network(fd)
        self.group = Group()
        self.logger = logging.getLogger(self.tag)
        self.logger.setLevel(1)
        self.formatter = CuteFormatter(maxbytes=400, encoding=self.encoding)
        self.connected = fd is not None
        if self.connected:
            self.me = me
        else:
            self.me = (self.nick, None, None)

    def __repr__(self):
        return u"Irc(tag=%s)" % self.tag

    ############################################################################################### core

    def _run(self):
        """
            greenlet starts here
            connect to irc, serve in a loop
            run self.disconnect() and self.onunload() on GreenletExit and die
        """
        self.onload()                               # let it fail
        try:
            while True:
                if not self.connected:
                    self.connect()                  # let it fail (should not happen, relly)
                    for chan in self.chans:
                        self.joinchan(chan)
                while True:
                    try:
                        line = self.net.getline()
                        line = line.decode(self.encoding)
                        try:
                            msg = Message(irc=self, line=line)
                        except MessageMalformed as e:
                            self.onexception(e, unexpected=True)
                            continue
                        self.onmessage(msg)
                        if type(msg) == Message and msg.command == "ping":
                            self.send("PONG %s" % msg.params[0])
                        elif type(msg) == Numeric and msg.num == 1:
                            self.me = (msg.target, None, None)
                            self.onconnected(msg)
                            self.privmsg(msg.target, "id")
                        elif msg.frommyself:
                            self.me = msg.sender
                            self.formatter.maxbytes = 512 - 7 - len("".join(self.me).encode(self.encoding))    # :nick!user@host <PRIVMSG :text>+\r\n"
                            self.logger.log(OTHER, "i am {0[0]}!{0[1]}@{0[2]} and i can send {1} bytes".format(self.me, self.formatter.maxbytes))
                    except ConnectionFailed as e:
                        self.onexception(e, unexpected=True)
                        self.disconnect()
                        break
                    except GreenletRehash:          # don't disconnect
                        raise
                    except GreenletExit:            # same as above, but disconnect
                        self.disconnect()           # let it fail (should not happen, relly)
                        raise
                    except Exception as e:
                        self.onexception(e, unexpected=True)
        finally:
            self.onunload()                         # let it fail

    def shutdown(self, exception=GreenletExit):
        """
            kills sender greenlet, all greenlets in group, oneself
            this will cause _run to exit and the thing should get deleted from memory
            ! if exception is GreenletExit, disconnects
        """
        self.group.kill(exception, block=False)
        self.kill(exception, block=False)

    ############################################################################################### my cute methods

    def send(self, data, log=True):
        """ encodes and sends one line """
        self.net.send(data.encode(self.encoding) + "\r\n")
        self.onsent(data, log)

    def connect(self):
        """ connects to servers[currectserver] """
        delay = 0
        while True:
            for server in self.servers:
                try:
                    self.onconnect(server)
                    self.net.connect(server.address, server.ssl)
                    self.send(u"NICK {0.nick}".format(self))
                    self.send(u"USER {0.username} lol wut :{0.realname}".format(self))
                    self.connected = True
                    return
                except ConnectionFailed as e:
                    self.onexception(e)
                    sleep(10 + delay)
                    delay += 1

    def disconnect(self):
        """ good-bye! """
        try:
            self.ondisconnect()
        finally:
            self.net.disconnect()
            self.connected = False

    def notice(self, target, line, *args, **kwargs):
        line = self.formatter.format(line, *args, shortenby=(9 + len(target.encode(self.encoding))), **kwargs)
        self.send(u"NOTICE " + target + " :" + line, False)
        self.onsentnotice(target, line)

    def privmsg(self, target, line, *args, **kwargs):
        line = self.formatter.format(line, *args, shortenby=(10 + len(target.encode(self.encoding))), **kwargs)
        self.send(u"PRIVMSG " + target + " :" + line, False)
        self.onsentprivmsg(target, line)

    def action(self, target, line, *args, **kwargs):
        line = self.formatter.format(line, *args, shortenby=(19 + len(target.encode(self.encoding))), **kwargs)
        self.send(u"PRIVMSG " + target + u" :\x01ACTION " + line + u"\x01", False)
        self.onsentaction(target, line)

    def joinchan(self, chan):
        self.send(u"JOIN " + chan)

    ############################################################################################### replace me

    def onconnect(self, server):
        """ called when we *start* connecting """
        self.logger.log(OTHER, "connecting to %s..." % server)

    def onconnected(self, msg):
        """ called when we have successfully connected to a server """
        self.logger.log(OTHER, "connected to %s!" % msg.sender[0])

    def ondisconnect(self):
        """ called when we disconnect """
        self.logger.log(OTHER, "disconnecting")

    def onload(self):
        """ called when the thing starts """
        self.logger.log(OTHER, "loading")

    def onunload(self):
        """ called when the thing dies """
        self.logger.log(OTHER, "unloading")

    def onexception(self, e, unexpected=False):
        """ called when any bot's internal exception occurs (the exception gets handled) """
        if unexpected:
            self.logger.exception(unicode(e))
        else:
            self.logger.error(unicode(e))

    ###

    def onmessage(self, msg):
        """ called when the thing receives any irc message """
        if type(msg) == Privmsg:
            self.onprivmsg(msg)
        elif type(msg) == Action:
            self.onaction(msg)
        else:
            self.logger.log(IN, msg.line)

    def onprivmsg(self, msg):
        dt = msg.sender[0] if msg.target == self.me[0] else msg.target
        self.logger.log(IN_PRIVMSG, "%s | <%s> %s", dt, msg.sender[0], msg.message)

    def onaction(self, msg):
        self.logger.log(IN_ACTION, "%s | * %s %s", msg.target, msg.sender[0], msg.message)

    ###

    def onsent(self, text, unprocessed):
        """ called on every send. if unprocessed is True, onsenetprivmsg and the sech have not been called """
        if unprocessed:
            self.logger.log(OUT, text)

    def onsentprivmsg(self, target, text):
        self.logger.log(OUT_PRIVMSG, "%s | <%s> %s", target, self.me[0], text)

    def onsentnotice(self, target, text):
        self.logger.log(OUT_NOTICE, "%s | <%s> %s", target, self.me[0], text)

    def onsentaction(self, target, text):
        self.logger.log(OUT_ACTION, "%s | * %s %s", target, self.me[0], text)

for setting in ["encoding", "network", "nick", "username", "password", "nickservpassword", "realname", "chans", "master"]:
    setattr(Irc, setting, property((lambda setting: lambda self: conf.get(setting, self.tag))(setting)))
setattr(Irc, "servers", property(lambda self: conf.getservers(self.tag)))

###################################################################################################
################################################################################################### message
###################################################################################################

class Message(object):
    """
        serializable message abstraction
        if neither irc intsance nor line is present, assume that
        attributes would be assigned from outside and do nothing
        raises MessageMalformed

        *:
            line = original text from the server
            sender = (nick, user, host) or (sender, ) or ()
            nick = nick   ?
            user = user   ?
            host = host   ?
            frommyself = True, False
            fromhuman = True, False
            frommaster = True, False

        privmsg / notice:
            _irc = reference to Irc instance
            _replyto = target of reply()
            target = #chan or nick
            message = my cute message
            splitmsg = [my, cute, message]
            tomyself = True, False

        join:
            target = #chan
            login = login or None
            realname = my real name or None

        part:
            target = #chat
            message = my part message

        quit:
            message = my quit message

        kick:
            target = #chan
            whom = kicked_guys_nick
            reason = kick reason    ?

        nick:
            newnick = new_nick

        account:
            login = new_login or None

        topic:
            target = #chan
            topic = new channel topic

        mode:
            target = #chan or nick
            mode = [various, parameters]

        numeric:
            num = 123
            target = bot_nick
            params = [possibly, empty, list, of, parameters]

        (other):
            command = "lowercasecommand"
            params = [list, of, parameters]

        a message of type Message identifies a message that hasn't
        been parsed by the module. it may or may not be malformed
    """
    def __init__(self, line=None, irc=None):
        if line is None:
            return
        self.line = line
        # split the line into parts, treating stuff after " :" as a single item
        try:
            parts = line.split(u" :", 1)
            parts = parts[0].split(None) + [parts[1]]
        except:
            parts = line.split(None)
        # identify the sender, command and params
        if parts[0].startswith(u":"):
            mask = string_to_mask(parts[0][1:])
            if mask[-1]:
                self.nick, self.user, self.host = self.sender = mask
            else:
                self.sender = (mask[0],)
            command, params = parts[1], parts[2:]
        else:
            self.sender = ()
            command, params = parts[0], parts[1:]
        # parse individual commands
        try:
            self.__class__ = {
                "privmsg": Privmsg,
                "notice": Notice,
                "join": Join,
                "part": Part,
                "quit": Quit,
                "kick": Kick,
                "nick": Nick,
                "account": Account,
                "topic": Topic,
                "mode": Mode
            }[command.lower()]
        except KeyError:
            try:
                self.num = int(command)
            except ValueError:                                                  # (OTHER)
                self.command = command.lower()
                self.params = params
            else:                                                               # NUMERIC
                self.__class__ = Numeric
                try:
                    self.target = params.pop(0)
                except IndexError:
                    raise MessageMalformed(line)
                self.params = params
        else:                                                                   # ALL THE OTHER COMMANDS
            # fail if not enough parameters
            if type(self) not in (Message, Quit, Numeric, Account, Part, Join, Nick):
                if len(params) < 2:
                    raise MessageMalformed(line)
            elif type(self) in (Part, Join, Nick):
                if len(params) < 1:
                    raise MessageMalformed(line)
            # parse known commands
            if isinstance(self, TextMessage):
                self.__init__(params, irc)
            else:
                self.__init__(params)
        # this is helpful
        self.fromhuman = len(self.sender) == 3
        self.frommyself = self.fromhuman and self.nick == irc.me[0]

    # also this
    @property
    def frommaster(self):
        try:
            return self._frommaster
        except AttributeError:
            self._frommaster = self.fromhuman and re.match(self._irc.master, mask_to_string(self.sender))
            return self._frommaster

    def __getitem__(self, key):
        if type(key) == int:
            return self.splitmsg[key]
        elif type(key) == slice:
            return " ".join(self.splitmsg[key])
        raise IndexError

    def __len__(self):
        return len(self.splitmsg)

    def __repr__(self):
        return "%s(%s)" % (self.__class__, self.__dict__)

    def __getstate__(self):
        dic = copy.copy(self.__dict__)
        try:
            del dic["_irc"], dic["_replyto"]
        except KeyError:
            pass
        return dic

class Numeric(Message):
    pass

class TextMessage(Message):
    """
        provides convenience reply / ireply / action funcions
        note: it is going to fail if self._irc is not present!
    """
    def __init__(self, params, irc):
        if irc:
            self._irc = irc
        try:
            self.target, self.message = params[:2]
        except ValueError:
            self.target, self.message = params[0], ""
        self.splitmsg = self.message.split()
        self._replyto = self.sender[0] if irc.me[0] == self.target else self.target
        if type(self) == Privmsg:
            if len(self.splitmsg) > 0 and self.splitmsg[0].lower().startswith("\x01action") and self.message[-1] == "\x01":           # PRIVMSG → ACTION
                self.__class__ = Action
                self.splitmsg = self.splitmsg[1:]
                if self.splitmsg:
                    self.splitmsg[-1] = self.splitmsg[-1][:-1]
                self.message = self.message[8:-1]
            else:
                self.command = None         # if privmsg and not action: command is None
        self.tomyself = self.target == irc.me[0]

    def reply(self, line, *args, **kwargs):
        if not self.tomyself:
            line = self.nick + ": " + line
        self._irc.privmsg(self._replyto, line, *args, **kwargs)

    def ireply(self, line, *args, **kwargs):
        self._irc.privmsg(self._replyto, line, *args, **kwargs)

    def action(self, line, *args, **kwargs):
        self._irc.action(self._replyto, line, *args, **kwargs)

    def mute(self):
        self.reply = self.ireply = self.action = lambda *a, **ka: None

class Privmsg(TextMessage):
    pass
class Notice(TextMessage):
    pass
class Action(TextMessage):
    pass

class Join(Message):
    def __init__(self, params):
        self.chan, self.login, self.realname = \
            params if len(params) == 3 \
            else (params[0], None, "")
        if self.login == "*":
            self.login = None

class Part(Message):
    def __init__(self, params):
        self.target = params[0]
        self.message = params[1] if len(params) > 1 else ""

class Quit(Message):
    def __init__(self, params):
        self.message = params[0] if len(params) > 0 else ""

class Kick(Message):
    def __init__(self, params):
        (self.target, self.whom), self.reason = params[:2], \
            (params[2] if len(params) > 2
                else "")

class Nick(Message):
    def __init__(self, params):
        self.newnick = params[0]

class Account(Message):
    def __init__(self, params):
        self.login = params[0] if params[0] != "*" else None

class Topic(Message):
    def __init__(self, params):
        self.target, self.topic = params[:2]

class Mode(Message):
    def __init__(self, params):
        self.target, self.mode = params[0], params[1:]
