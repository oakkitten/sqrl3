#!/usr/bin/python
# -*- coding: utf-8 -*-

""" plugin description """

from sqrl3.script import onprivmsg, g_meta

############################################################ admin

@onprivmsg("rehash", "r", kingly=True)
def rehash(self, msg):
    """ rehash: reloads the script without disconnecting """
    from sqrl3.sqrl import rehash
    msg.reply("rehashing!")
    rehash("requested")

@onprivmsg("load", kingly=True)
def load(self, msg):
    """ load [name]: loads one script """
    if not len(msg): msg.reply("usage: load name")
    elif self.loadscript(msg[0]): msg.reply("loaded: `{0}`", msg[0])
    else: msg.reply("couldn't load `{0}`", msg[0])

@onprivmsg("unload", block=True, kingly=True)
def unload(self, msg):
    """ unload [name]: unloads one script """
    if not len(msg): msg.reply("usage: unload name")
    elif self.unloadscript(msg[0]): msg.reply("unloaded: `{0}`", msg[0])
    else: msg.reply("couldn't load `{0}`", msg[0])

############################################################ help

@onprivmsg("list")
def listcommands(self, msg, scripts):
    """ list: lists commands """
    l = {}
    for script in scripts:
        l.update(g_meta[script].commands)
    msg.reply("usable commands: " + ", ".join(l.iterkeys()))

@onprivmsg("help")
def helpcommand(self, msg, scripts):
    """ oh really? """
    if not len(msg): msg.reply(u"usage: help command. try `list` for a list of commands")
    else:
        for script in scripts:
            if msg[0] in g_meta[script].commands:
                msg.reply(g_meta[script].commands[msg[0]])
                return
        msg.action(u"didn't find `{0}`", msg[0])
