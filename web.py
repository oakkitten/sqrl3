#!/usr/bin/python
# -*- coding: utf-8 -*-

""" provides various web utilities """

import re
import urllib2
import copy

__all__ = "re_http", "opener", "opener_en", "opener_ru", "clean"

############################################################ re

str_http = ur"""
    (?:^|\s|\()              # preceded by start of the string, a space or a (
        (
            (?:https?://)?   # http:// (optional)
            [\w\d\.-]+       # www.mail
            \.               # .
            (?:              # рф/com/museum
                \w{2}
                |com|org|edu|gov|int|mil|net|biz|pro|tel|xxx
                |arpa|asia|info|name|aero|coop|jobs|post
                |museum|travel
            )
            (?:/\S*?)?       # whatever / + non-space that follow mail.ru (/abc?def&ghi)
        )
    [,.)!?:]*(?=\s|$)        # except punctuation and following spaces
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
