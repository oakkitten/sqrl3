#!/usr/bin/python
# -*- coding: utf-8 -*-

""" provides irc connection abstraction """

import re
from StringIO import StringIO
from fnmatch import fnmatch

################################################################

def first_line(string):
    """
        get first line of a string, stripped
    """
    return StringIO(string).readline().strip()

def color(string, color):
    """
        colors string using colors 0--8
        BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE
    """
    return "\033[1;%sm%s\033[0m" % (color+30, string)

def ischannel(target):
    return target[0] in ("#", "&")

_re_mask = re.compile(r"^([^!@]+)(?:(?:!([^@]+))?@([^ ]+))?$")
def string_to_mask(s):
    return _re_mask.match(s).groups()

def mask_to_string(m):
    mask, user, host = m
    if host:
        if user:
            mask += "!" + user
        mask += "@" + host
    return mask

################################################################

def get_args(func):
    """
        for a function, return:
        * variables without defaults
        * variables with defaults
        * defaults
    """
    varnames = func.func_code.co_varnames[:func.func_code.co_argcount]
    defaults = func.func_defaults
    if defaults:
        ld = len(defaults) if defaults else 0
        return varnames[:-ld], varnames[-ld:], defaults
    else:
        return varnames, None, None

def get_argcount(func):
    return func.func_code.co_argcount

################################################################

from string import Formatter
class CuteFormatter(Formatter):
    """
        adds to the Formatter's syntax stuff like:
            {0:R} - truncate text from the right, if needed, replacing the end with …
            {1:15M} - same, except text will not exceed 15 bytes and will be chopped in the middle
            {0!q:5R} - in addition to truncating, quote text (inside the quotes).
                       there's poor man's detection of Russian and Engish, too
        the necessity to cut stuff is determined by itilializers:
            maxbytes - the maximum bytes that formatter can output (can output less then maxbytes due to stripping)
            sortenby (format's keyword parameter) - bytes to cut from maxbytes
            encoding
        does not raise anything (expect some Unicode errors if you pass non-unicode-convertable stuff)
        pretty slow! :<
    """
    def __init__(self, maxbytes=510, encoding="utf-8"):
        assert maxbytes >= 3
        self.maxbytes, self.encoding = maxbytes, encoding
        self.dots8 = u"…".encode(encoding)
        self.dots8len = len(self.dots8)
        self.quotesen, self.quotesru, self.quotesjp = (tuple(quote.encode(encoding) for quote in pair)
                                                       for pair in ((u"“", u"”"), (u"«", u"»"), (u"「", u"」")))

    def vformat(self, format_string, args, kwargs):
        maxbytes, encoding, dots8, dots8len = self.maxbytes, self.encoding, self.dots8, self.dots8len
        try:
            maxbytes -= kwargs["shortenby"]
        except:
            pass
        result8, leftovers = [], []
        for literal_text, field_name, format_spec, conversion in self.parse(format_string):
            if literal_text:
                result8.append(literal_text.encode(encoding))
            if field_name is not None:
                obj, arg_used = self.get_field(field_name, args, kwargs)
                if len(format_spec) > 0 and format_spec[-1] in ("R", "M"):          # |_ is this {field} R/maximum stuff?
                    try:
                        limit = int(format_spec[:-1]) or 9999
                    except ValueError:
                        limit = 9999
                    if conversion and conversion.endswith("q"):                     #     |_ do we need quotes?
                        if len(conversion) > 1:                                     #           self.convert_field doesn't accept empty strings
                            obj = self.convert_field(obj, conversion[:-1])
                        text = unicode(obj)
                        q1, q2 = self.quote(text)
                        text8 = text.encode(encoding)
                        idx = len(result8) + 1
                        result8 += [q1, None, q2]
                    else:                                                           #     |_ we don't!
                        obj = self.convert_field(obj, conversion)
                        text8 = unicode(obj).encode(encoding)
                        idx = len(result8)
                        result8.append(None)
                    leftovers.append([idx, text8, min(len(text8), limit),           #           idx, "text", len(text)/imposed limit
                                     format_spec[-1], len(text8) > limit])          #           "R", truncating?
                else:                                                               # |_ ordinary stuff!
                    if conversion and conversion.endswith("q"):                     #     |_ do we need quotes?
                        if len(conversion) > 1:                                     #           self.convert_field doesn't accept empty strings
                            obj = self.convert_field(obj, conversion[:-1])
                        q1, q2 = self.quote(unicode(obj))
                        text8 = self.format_field(obj, format_spec).encode(encoding)
                        result8.append(q1 + text8 + q2)
                    else:                                                           #     |_ we don't
                        obj = self.convert_field(obj, conversion)
                        text8 = self.format_field(obj, format_spec).encode(encoding)
                        result8.append(text8)
        if len(leftovers):                                                          # |_ do we have :R / :M?
            result8len = sum(len(item) for item in result8 if item)
            leftovers8len = sum(item[2] for item in leftovers)
            can_add = maxbytes - result8len
            if can_add > 0 and result8len+leftovers8len > maxbytes:                 #   |_ we have, but do we have room and do we need to cut stuff?
                deltas, added = [], 0                                               #     |_ we do, decrease limit as needed
                for (n, leftover) in enumerate(leftovers):
                    min_len_limit = leftover[2]
                    hardlimit = (min_len_limit * can_add / leftovers8len)
                    leftover[2] = hardlimit
                    added += hardlimit
                    deltas.append((min_len_limit - hardlimit, n))                   #           how many chars removed from where
                diff = can_add - added                                              #           between added amount (add) and max amount (can_add)
                if diff:
                    for (delta, n) in sorted(deltas):                               #           start with the smallest changes
                        if diff >= delta and not leftovers[n][4]:                   #           add back letters ONLY if it HELPS and the thing is not being
                                leftovers[n][2] += delta                            #               truncated anyway!
                                diff -= delta
                    leftovers[n][2] += diff                                         #           if we have bytes left, add them to the biggest cut
            else:                                                                   #     |_ we either have no room or don't need to cut stuff.
                can_add = leftovers8len                                             #        in both cases, insert stuff (cutting it by numbers in {}s)!
            for (n, text8, limitwithdots, mode, truncated) in leftovers:            #   |_ for each leftover:
                if len(text8) > limitwithdots:                                      #     |_ if length exceeds the field, cut!
                    limit = limitwithdots - dots8len
                    if limit <= 0:
                        text8 = "..."[:limitwithdots]
                    elif mode == "R":
                        text8 = text8[:limit].strip() + dots8
                    else:
                        half = limit / 2
                        text8 = text8[:half].strip() + dots8 + text8[-half-1 if limit % 2 else -half:].strip()
                result8[n] = text8                                                  #     |_ and append the leftover to the result
        result8 = "".join(result8)
        if len(result8) > maxbytes:
            result8 = result8[:maxbytes-dots8len] + dots8
        return result8.decode(encoding, "ignore")

    def quote(self, value):
        for x in value[:10]:
            if u"\u0400" <= x <= u"\u04ff":                                         # roughly russian alphabet in unicode
                return self.quotesru
            if u"\u3000" <= x <= u"\u30ff" or u"\u4e00" <= x <= u"\u9faf":          # roughly punctuation, kanas and unified CJK shit
                return self.quotesjp
        return self.quotesen
