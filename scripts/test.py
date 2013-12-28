#!/usr/bin/python
# -*- coding: utf-8 -*-

""" plugin description """

from sqrl3.script import onprivmsg, onnumeric

@onprivmsg
def talk(self, msg, talkative=True):
    if talkative and not msg.command and not msg.tomyself and len(msg) and msg[0][:-1] == self.me[0]:
        msg.reply("bla bla bla")

@onprivmsg("whois")
def whois(self, msg):
    self.send("whois sqrl")

@onnumeric(312)
def n372(self, msg):
    print u"====================== ♥"

@onprivmsg("longmessage")
def longmessage(self, msg):
    msg.reply(u"lolwut there goes long message: {!q:R}", "".join(u"%sоче нь дли нн ый %sсоо бще ние " % (x, x) for x in range(50)))

@onprivmsg("fail")
def fail(self, msg):
    a = 1 / 0
