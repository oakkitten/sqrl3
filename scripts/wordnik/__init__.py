#!/usr/bin/python
# -*- coding: utf-8 -*-

""" wordnik definitions  """

from ...script import onload, onprivmsg
from ...constants import ResultNotFound
from .wordnik import initialize, definition, suggestions
from gdshortener import ISGDShortener
from urllib2 import quote


isgd = ISGDShortener()


@onload
def load(self, wordnik_key):
    initialize(wordnik_key)


@onprivmsg("define", "d")
def privmsg(self, msg):
    """ returns wordnik word definition or suggestions"""
    word = msg[:]

    try: d = definition(word)
    except ResultNotFound: d = None

    try: s = ', '.join(suggestions(word))
    except ResultNotFound: s = None

    if d: fmt = u"{d:R} — {u} — did you mean {s}?" if s else u"{d:R} — {u}"
    elif s: fmt = u"did you mean {s}?"
    else:
        msg.action(u"failed: couldn't find the word in wordnik")
        return

    url = "https://www.wordnik.com/words/" + quote(word.encode('utf-8'))
    try: url = isgd.shorten(url)[0]
    except: pass

    msg.reply(fmt, d=d, u=url, s=s)
