#!/usr/bin/python
# -*- coding: utf-8 -*-

""" plugin description """

from sqrl3.script import onprivmsg

@onprivmsg
def talk(self, msg, talkative=True):
    if talkative and not msg.command and not msg.tomyself and len(msg) and msg[0][:-1] == self.me[0]:
        msg.reply("bla bla bla")
