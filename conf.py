#!/usr/bin/python
# -*- coding: utf-8 -*-

""" preferences """

# WARNING: Do not edit this file to change the settings!
# Please run this script to create the setting file in ~/.sqrl.json

from constants import ConfigMalformed, ConfigDoesNotExist, ServerMalformed
import codecs, json, re
from os.path import expanduser
from itertools import cycle
from copy import deepcopy

FILE = "~/.sqrl.json"
DEFAULT = {
    "networks": {
        "example": [
            "nonsslserver 6667 myserverpassword",
            "sslserver +9999"
        ],
        "freenode": [
            "chat.freenode.net 6667",
            "asimov.freenode.net +7000"
        ],
        "efnet": [
            "8.7.233.233 +9999",
            "8.7.233.238 +9999",
            "198.3.160.3 +9999"
        ]
    },
    "connections": {
        "default": {
            "network": None,
            "nick": "sqrl",
            "username": "sqrl",
            "password": None,
            "nickservpassword": None,
            "realname": u"i'm a cute li'l bot! say “-help” to me",
            "chans": {},
            "scripts": [
                "utils", "ignore"
            ],
            "master": "[^@]+@unaffiliated/squirrel",
            "encoding": "utf-8",
            "mute": False,
            "prefix": "-"
        },
        "myfreenode": {
            "network": "freenode",
            "password": ":myfreenodelogin myfreenodepass",
            "nickservpassword": "myfreenodepass",
            "chans": {
                "##chan123": {"scripts": [""]},
                "##chan456": {"mute": True}
            }
        }
    }
}

##########################################################################################
##########################################################################################
##########################################################################################

_config = _tags = _networks = _default = None

def read(filename):
    """
        returns an object with config from the specified file. format = json
        raises: ConfigDoesNotExist, MalformedConfig, IOError+
    """
    global _config, _tags, _networks, _default
    try:
        with codecs.open(expanduser(filename), "r", "utf-8") as f:
            conf = json.load(f)
            _config, _tags, _networks, _default = \
                conf, conf["connections"], conf["networks"], conf["connections"]["default"]
    except IOError as e:
        if e.errno == 2:
            raise ConfigDoesNotExist
        else:
            raise
    except (AssertionError, TypeError, ValueError, OverflowError) as e:
        raise ConfigMalformed(e)

##########################################################################################

def write(filename):
    """
        writes config to file. !does not! create path if necessary. format = json
        raises: MalformedConfig, IOError+
    """
    try:
        with codecs.open(expanduser(filename), "w", "utf-8") as f:
            json.dump(_config, f, ensure_ascii=False, indent=4)
    except (TypeError, ValueError, OverflowError) as e:
        raise ConfigMalformed(e)


##########################################################################################
##########################################################################################
##########################################################################################

_networks_processed = {}

def _geted(name, tag, chan):
    con = _tags[tag]
    if chan:
        try: return con["chans"][chan][name]
        except KeyError: return deepcopy(get(name, tag))
    else:
        try: return con[name]
        except KeyError: return deepcopy(_default[name])

##########################################################################################

def get(name, tag, chan=None):
    con = _tags[tag]
    if chan:
        try: return con["chans"][chan][name]
        except KeyError: pass
    try: return con[name]
    except KeyError: return _default[name]

def getdefault(name, tag, chan=None, default=None):
    try: return get(name, tag, chan)
    except KeyError: return default

##########################################################################################

def set(name, value, tag, chan=None):
    if chan: _tags[tag]["chans"].setdefault(chan, {})[name] = value
    else: _tags.setdefault(tag, {})[name] = value

def append(name, value, tag, chan=None):
    item = _geted(name, tag, chan)
    item.append(value)
    set(name, item, tag, chan)

def remove(name, value, tag, chan=None):
    item = _geted(name, tag, chan)
    item.remove(value)
    set(name, item, tag, chan)

##########################################################################################

def getservers(tag):
    network = _tags[tag]["network"]
    try: return _networks_processed[network]
    except KeyError: return _networks_processed.setdefault(network, cycle([Server(s) for s in _networks[network]]))

def getconnections():
    for tag in _tags:
        if tag != "default":
            yield tag

##########################################################################################
##########################################################################################
##########################################################################################

re_server = re.compile(r"^(\S+)(?:\s+(\+)?(\d+))?$")
class Server(object):
    """
        server abstraction
        string: server.address [+]1234
        raises ServerMalformed
    """
    def __init__(self, string):
        try:
            host, ssl, port = re_server.match(string).groups()
            self.address, self.ssl = (host, int(port)), bool(ssl)
        except AttributeError:
            raise ServerMalformed(string)
        self.string = string

    def __str__(self):
        return self.string

    __slots__ = "string", "address", "ssl"
