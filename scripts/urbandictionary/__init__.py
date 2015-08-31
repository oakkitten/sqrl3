#!/usr/bin/python
# -*- coding: utf-8 -*-

""" urban dictionary """

from sqrl3.script import onprivmsg
from .urbandictionary import urbandictionary


@onprivmsg("urbandictionary", "ud")
def privmsg(self, msg):
    """ returns urbandictionary word definition """
    msg.reply("\x02{0}\x02: {1} ({3}/{4}) {2:R}", *urbandictionary(msg[:]))
