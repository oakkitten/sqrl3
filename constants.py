#!/usr/bin/python
# -*- coding: utf-8 -*-

""" collection of bot errors and other constants """

from gevent import GreenletExit

IN, OUT, OTHER = 20, 30, 50
IN_PRIVMSG, IN_ACTION, IN_NOTICE = 21, 22, 23
OUT_PRIVMSG, OUT_ACTION, OUT_NOTICE = 31, 32, 33

class GreenletRehash(GreenletExit):
    """ used to restart the bot without disconnecting """

########################################################################################## base

class BotException(Exception):
    """ base exception for the bot """

class ApplicationShutdown(BotException):
    """ disconnect and shutdown application """

########################################################################################## config

class ConfigError(BotException):
    """ base exception for config errors """

class ConfigDoesNotExist(ConfigError):
    """ raised when the file does not exist """

class ConfigMalformed(ConfigError):
    """ config file or config data is invalid due to json error or missing keys """

########################################################################################## connection

class ConnectionFailed(BotException):
    """ raised by Network when connection fails and has to be reinitiated
    usage: raise ConnectionFailed(socketerror) """

class ConnectionTimeout(ConnectionFailed):
    """ raised on connect() or getline()-like functions """

class ConnectionTerminated(ConnectionFailed):
    """ raised when connection has been terminated by server """

########################################################################################## misc

class ServerMalformed(BotException):
    """ raised with server string is malformed """

class MessageMalformed(BotException):
    """ raised when bot can't parse server message """

########################################################################################## misc

class HaltMessage(BotException):
    """ raised when a greenlet wants to stop other scripts from processing the message """

class MuteMessage(BotException):
    """ raise when a greenlet wants to mute other scripts, that is, prevent them from using msg.reply """

########################################################################################## general stuff

class ResultNotFound(BotException):
    """ raised when database query was processed successfully but no item was found """

class ResultNotUnderstood(BotException):
    """ raised when database query was not processed successfully """
