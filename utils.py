#!/usr/bin/python
# -*- coding: utf-8 -*-

""" provides irc connection abstraction """

import re
from StringIO import StringIO

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
    return "\033[1;%sm%s\033[0m" % (color + 30, string)

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

_inf = float("inf")

from string import Formatter
class CuteFormatter(Formatter):
    """
        adds to the Formatter's syntax stuff like:
            {:r} - truncate text from the right, if needed, replacing the end with …
            {:R} - same as r, except the remainder then can be found in instance.more
                   if there's no R, instance.more is set to ""
            {1:15m} - same, except text will not exceed 15 bytes and will be chopped in the middle
            {url!q} - in addition to truncating, put quotes around the text
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
        self.more = ""

    def vformat(self, format_string, args, kwargs):
        # result8 = [
        #    a list of parts of the string that are sure to be added for leftovers,
        #    also some Nones if somethings is to be added later
        # ]
        # leftovers = [[
        #   idx,            # 0: index of corresponding None in result8
        #   text8,          # 1: encoded "string with corresponding text"
        #   limit,          # 2: max no of bytes that the field can contain, or len(text8), or maxbytes, whichever less
        #   format_spec     # 3: "r", "R" or "m"
        # ]]
        maxbytes, encoding, dots8, dots8len = self.maxbytes, self.encoding, self.dots8, self.dots8len
        if "shortenby" in kwargs:
            maxbytes -= kwargs["shortenby"]
        result8, leftovers, lastauto = [], [], 0
        self.more = ""
        for literal_text, field_name, format_spec, conversion in self.parse(format_string):
            if literal_text:
                result8.append(literal_text.encode(encoding))
            if field_name is not None:
                if field_name == "":
                    field_name = str(lastauto)
                    lastauto += 1
                obj, arg_used = self.get_field(field_name, args, kwargs)
                if len(format_spec) > 0 and format_spec[-1] in ("r", "m", "R"):
                    # this field is r / R / m
                    # find out the limit, conver and retreive quotes as needed
                    # append quotes and None to result8
                    # and append according record to leftovers
                    try: limit = int(format_spec[:-1]) or _inf
                    except ValueError: limit = _inf
                    if conversion and conversion.endswith("q"):
                        if len(conversion) > 1:
                            obj = self.convert_field(obj, conversion[:-1])
                        text = unicode(obj)
                        q1, q2 = self.quote(text)
                        text8 = text.encode(encoding)
                        idx = len(result8) + 1
                        result8 += [q1, None, q2]
                    else:
                        obj = self.convert_field(obj, conversion)
                        text8 = unicode(obj).encode(encoding)
                        idx = len(result8)
                        result8.append(None)
                    leftovers.append((idx, text8, min(len(text8), limit, maxbytes), format_spec[-1]))
                else:
                    # this is an ordinary field,
                    # but it still can contain !q
                    if conversion and conversion.endswith("q"):
                        if len(conversion) > 1:
                            obj = self.convert_field(obj, conversion[:-1])
                        q1, q2 = self.quote(unicode(obj))
                        text8 = self.format_field(obj, format_spec).encode(encoding)
                        result8.append(q1 + text8 + q2)
                    else:
                        obj = self.convert_field(obj, conversion)
                        text8 = self.format_field(obj, format_spec).encode(encoding)
                        result8.append(text8)

        if leftovers:
            # we have leftovers, means that there is something in :r/:R/:m to be added
            # get total length of non-Nones in result8 and
            # sum of length of strings in leftovers (len("text") or limit, whichever smaller)
            result8len = sum(len(item) for item in result8 if item)
            leftovers8len = sum(item[2] for item in leftovers)
            add_length = max(maxbytes - result8len, 0)
            # we have space left, so we can add some bytes
            # determine if we will have to cut
            we_are_cutting = result8len + leftovers8len > maxbytes
            # but we will have to cut the strings
            # start moving stuff from leftovers to result8 at once
            for idx, text8, full_limit, format_spec in leftovers:
                if we_are_cutting:
                    # adjust full_limit to max length it can take
                    limit_with_dots = full_limit * add_length / leftovers8len
                    if len(text8) > limit_with_dots:
                        # we need to cut this particular text
                        # we will have to add dots somewhere, so determine limit without dots now
                        limit = limit_with_dots - dots8len
                        if dots8len > limit_with_dots:
                            add8 = "..."[:limit_with_dots]
                        elif format_spec in ("r", "R"):
                            # check if there's a space in the last 20 bytes of the text[:limit]
                            # if there is, and it's not very far on the let, reduce limit to it
                            space_idx = text8.rfind(" ", max(0, limit - 20), limit)
                            if space_idx > dots8len:
                                limit = space_idx
                            add8 = text8[:limit].strip() + dots8
                            if format_spec == "R":
                                self.more = text8[limit:].strip().decode(encoding, "ignore")
                        else:
                            # mode = m
                            half = limit / 2
                            add8 = text8[:half].strip() + \
                                dots8 + \
                                text8[-half - 1 if limit % 2 else -half:].strip()
                    else:
                        add8 = text8
                else:
                    add8 = text8
                # we have determined the addition to result8
                # check if it's within the limits and
                # adjust remaining space & remaning bytes
                assert len(add8) <= full_limit
                add_length -= len(add8)
                leftovers8len -= full_limit
                result8[idx] = add8
        # result8 doesn't have any Nones now
        # but it still can be longer than maxbytes
        result8 = "".join(result8)
        if len(result8) > maxbytes:
            result8 = result8[:maxbytes - dots8len] + dots8
        return result8.decode(encoding, "ignore")

    def quote(self, value):
        for x in value[:10]:
            if u"\u0400" <= x <= u"\u04ff":                                         # roughly russian alphabet in unicode
                return self.quotesru
            if u"\u3000" <= x <= u"\u30ff" or u"\u4e00" <= x <= u"\u9faf":          # roughly punctuation, kanas and unified CJK shit
                return self.quotesjp
        return self.quotesen
