#!/usr/bin/python
# -*- coding: utf-8 -*-

from sqrl3.script import onprivmsg, onload
from sqrl3.web import re_http, opener_en, clean
from lxml import html, etree
from sqrl3.constants import BotException
import re
from bs4 import UnicodeDammit
from gevent.pool import Group
import urllib2

############################################################ triggers

@onload
def load(self):
    self.chans_urls = {}
    self.chans_processors = {}

@onprivmsg("title", onex=u"couldn't fetch the title: {!t}")
def cmdtitle(self, msg):
    """ title [url]: return url for a given string or the last mentioned url (and additional data for youtube) """
    if len(msg):
        res = title(msg[:])
        msg.reply(u"↑ " + res.longtemplate, *res.longargs)
    else:
        url = self.chans_urls[msg._replyto]
        res = title(url)
        msg.reply(u"{:30m}: " + res.longtemplate, url, *res.longargs)

@onprivmsg
def autotitle(self, msg, announce_title=True):
    if not msg.command:
        urls = re_http.findall(msg.message)
        if urls:
            self.chans_urls[msg._replyto] = urls[-1]
            try: p = self.chans_processors[msg._replyto]
            except KeyError: p = self.chans_processors[msg._replyto] = Processor()
            wasempty = p.empty()
            for url in urls:
                p.spawn(ptitle, url)
            if wasempty:
                p.join()
                vals = p.values()
                if len(vals) == 1:
                    val = vals[0]
                    if val:
                        msg.ireply(u"↑ " + val.longtemplate, *val.longargs)
                else:
                    temps, args = [], []
                    for val in vals:
                        if val:
                            temps.append(val.shorttemplate)
                            args.extend(val.shortargs)
                        else:
                            temps.append(u"…")
                    if args:
                        msg.ireply(u"↑ " + ", ".join(temps), *args)

############################################################ processor

class Processor(object):
    def __init__(self):
        self.group = Group()
        self.greenlets = []

    def spawn(self, func, *args, **kwargs):
        g = self.group.spawn(func, *args, **kwargs)
        self.greenlets.append(g)

    def join(self):
        self.group.join()

    def values(self):
        gs, self.greenlets = self.greenlets, []
        return [g.value for g in gs]

    def empty(self):
        return not bool(self.greenlets)

############################################################ pretty obvious?

def ptitle(url):
    try: return title(url)
    except: pass

def title(url):
    try: return Youtube(url)
    except: return Title(url)

############################################################# too many exceptions?

class CantGetContents(BotException):
    pass

class ThereIsNoTitle(BotException):
    pass

class ThereIsNoContentType(BotException):
    pass

class ThisIsNotHTML(BotException):
    pass

class MeaninglessTitle(BotException):
    pass

#############################################################

x_title = etree.XPath(".//title[1]")
class Title(object):
    """
        this class, and all similar classes, take url and produce the following properties:
          * shorttemplate = "{}": template for the following
          * shortargs: a tuple consisting of arguments for the template
          * longtemplate
          * longargs: these two can have additional details such as video description
        if can't get a title, fail
    """
    def __init__(self, url):
        if not url.startswith("http"):
            url = "http://" + url
        try: resp = opener_en.open(url.encode("utf-8"), timeout=5)
        except urllib2.URLError as e: raise CantGetContents(e)
        try: ctype = resp.info()["content-type"]
        except KeyError: raise ThereIsNoContentType("there's no content-type")
        if ("/html" not in ctype) and ("/xhtml" not in ctype):
            raise ThisIsNotHTML("this doesn't look like html")

        data = resp.read(262144)
        encoding = UnicodeDammit(data[:5000], is_html=True).original_encoding or UnicodeDammit(data, is_html=True).original_encoding
        title = x_title(html.fromstring(data, parser=html.HTMLParser(encoding=encoding)))
        if not title:
            raise ThereIsNoTitle(u"there's no title in the first 4⁹ bytes")
        title = title[0].text
        if title is None:
            raise MeaninglessTitle(u"title is present but empty")
        title = clean(title)

        if title == "imgur: the simple image sharer": raise MeaninglessTitle("who needs the default imgur title?")
        elif title.lower() in url.lower(): raise MeaninglessTitle("title text is contained within the url")
        self.shortargs = self.longargs = (title,)

    shorttemplate = longtemplate = "{!q:m}"


# http://www.youtube.com/watch?v=y71vHIdv5IM
# http://youtu.be/y71vHIdv5IM
# http://y2u.be/y71vHIdv5IM
re_youtube = re.compile(r"(?:youtube.com/watch\?(?:\S+?&)?v=|y(?:out|2)u.be/)([A-z0-9_-]+)")
namespaces = {"media": "http://search.yahoo.com/mrss/", "yt": "http://gdata.youtube.com/schemas/2007", "gd": "http://schemas.google.com/g/2005"}
class Youtube(object):
    def __init__(self, url):
        id = re_youtube.search(url).group(1)
        data = urllib2.urlopen("https://gdata.youtube.com/feeds/api/videos/%s?v=2" % id).read()
        tree = etree.fromstring(data)

        def first(xpath):
            return tree.xpath(xpath, namespaces=namespaces)[0]

        title = clean(first(".//media:title").text.splitlines()[0])
        rating = first(".//gd:rating").attrib["average"][:3]
        viewcount = first(".//yt:statistics").attrib["viewCount"]
        duration = s_to_ms(int(first(".//media:content").attrib["duration"]))

        self.shortargs = (title, duration, rating, viewcount)
        try: self.longargs = (title, duration, rating, viewcount, clean(first(".//media:description").text.splitlines()[0]))
        except: self.longtemplate, self.longargs = self.shorttemplate, self.shortargs

    shorttemplate = "{!q:m} ({}, {}, {})"
    longtemplate = "{!q:m} ({}, {}, {}): {:250R}"

def s_to_ms(s):
    m, s = divmod(s, 60)
    if m: return "%sm%ss" % (m, s)
    else: return "%ss" % s
