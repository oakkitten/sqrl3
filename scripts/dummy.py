#!/usr/bin/python
# -*- coding: utf-8 -*-

""" dummy """

from sqrl3.script import onprivmsg

@onprivmsg("dummy")
def privmsg(self, msg, prefix, sex="lol"):
    """ dummy dummy DUMMY """
    print "> dummy"
