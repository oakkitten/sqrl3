#!/usr/bin/python
# -*- coding: utf-8 -*-

""" provides various web utilities """

import re
import urllib2
import copy

__all__ = "re_http", "opener", "opener_en", "opener_ru", "clean"

############################################################ re

str_http = ur"""
    # url must be preceded by a space, a ( or a start of the string
    (?:(?<=\s|\()|(?<=^))

    # http:// or www
    (?:https?://|www\.)

    # optional user:pass at
    (?:\S+(?::\S*)?@)?

    (?:
        # ip address (+ some exceptions)
        (?!10(?:\.\d{1,3}){3})
        (?!127(?:\.\d{1,3}){3})
        (?!169\.254(?:\.\d{1,3}){2})
        (?!192\.168(?:\.\d{1,3}){2})
        (?!172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})

        (?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])
        (?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5])){2}
        (?:\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-4]))
    |
        # domain name (a.b.c.com)
        (?:(?:[a-z\u00a1-\uffff0-9]+-?)*[a-z\u00a1-\uffff0-9]+)     # a, a-b
        (?:\.(?:[a-z\u00a1-\uffff0-9]+-?)*[a-z\u00a1-\uffff0-9]+)*  # .c, .c-d
        (?:\.(?:[a-z\u00a1-\uffff]{2,}))                            # .ru, .com, etc
    )

    # port?
    (?::\d{2,5})?

    # / & the rest
    (?:
        /
        (?:
            # hello(world) in "hello(world))"
            (?:
                [^\s(]*
                \(
                [^\s)]+
                \)
            )+
            [^\s)]*
        |
            # any string (non-greedy!)
            \S*?
        )
    )?

    # url must be directly followed by:
    (?=
        # some possible punctuation
        # AND space or end of string
        [,.)!?:]*
        (?:\s|$)
    )
    """

re_http = re.compile(str_http, re.X | re.U)
re_spaces = re.compile("\s+")

############################################################ openers

opener = urllib2.build_opener()
opener.addheaders = [
    ('User-Agent', 'Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11'),
    ('Accept', 'text/html')]

opener_en = urllib2.build_opener()
opener_en.addheaders = [
    opener.addheaders[0],
    ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    ("Accept-Language", "en;q=0.8,ru;q=0.6")]

opener_ru = urllib2.build_opener()
opener_ru.addheaders = copy.copy(opener_en.addheaders)
opener_ru.addheaders[2] = (opener_ru.addheaders[2][0], "ru;q=0.8,en;q=0.6")

############################################################ openers

def clean(string):
    """
        return string without spaces on start and end
        also, compresses multiple spaces & \ns into one space
    """
    return re_spaces.sub(" ", string).strip()
