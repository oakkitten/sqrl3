#!/usr/bin/python
# -*- coding: utf-8 -*-

""" plugin description """

from sqrl3.script import onprivmsg, g_meta

################

@onprivmsg("rehash", "r", kingly=True)
def regash(self, msg):
    """ rehash: reloads the script without disconnecting """
    from sqrl3.sqrl import rehash
    msg.reply("rehashing!")
    rehash("requested")

@onprivmsg("load", kingly=True)
def loload(self, msg):
    """ load [name]: loads one script """
    if self.loadscript(msg[0]): msg.reply("loaded: " + msg[0])
    else: msg.reply("couldn't load " + msg[0])

@onprivmsg("unload", block=True)
def unloload(self, msg):
    """ unload [name]: unloads one script """
    if self.unloadscript("dummy"): msg.reply("unloaded: " + msg[0])
    else: msg.reply("couldn't load " + msg[0])

################

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
    if len(msg):
        for script in scripts:
            if msg[0] in g_meta[script].commands:
                msg.reply(g_meta[script].commands[msg[0]])
                return
    msg.action(u"didn't find {0!q}", msg[0])
