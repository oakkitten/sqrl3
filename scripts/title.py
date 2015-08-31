#!/usr/bin/python
# -*- coding: utf-8 -*-

from sqrl3.script import onprivmsg, onload
from sqrl3.web import re_http, opener_en
from sqrl3.utils import clean
from lxml import html, etree
from sqrl3.constants import BotException
import re
import chardet
from gevent.pool import Group
import urllib2, httplib2
from StringIO import StringIO
import gzip

############################################################ triggers

@onload
def load(self, yt_key=None):
    global youtube_key
    self.chans_urls = {}
    self.chans_processors = {}
    youtube_key = yt_key

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
                        msg.ireply(u"↑↑ " + ", ".join(temps), *args)

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

class ThisIsNotHTML(BotException):
    pass

class MeaninglessTitle(BotException):
    pass

#############################################################

x_title = etree.XPath(".//title[1]")
re_wikiurl = re.compile(r"""^https?://[\w-]+\.(?:m\.)?wikipedia.org""", re.U)
re_charset = re.compile(r"""<\s*meta[^>]+charset=(?:['"]\s*)?([A-z0-9-_]+)""", re.I)

def getcharset(data):
    r = re_charset.search(data)
    if r:
        return r.group(1)
    else:
        confidence, charset = chardet.detect(data[-5000:]).values()
        if confidence:
            try:
                unicode(data, charset)
                return charset
            except:
                pass
        return "utf-8"

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
        url = httplib2.iri2uri(url)

        # certain urls are self-explicable
        if re_wikiurl.match(url):
            try: assert urllib2.unquote(url.encode("ascii")).decode('utf8') != url
            except: raise MeaninglessTitle("wikipedia title is within the url")

        try: resp = opener_en.open(url.encode("utf-8"), timeout=5)
        except urllib2.URLError as e: raise CantGetContents(e)
        info = resp.info()
        if info.type not in ("text/html", "text/xhtml"):
            raise ThisIsNotHTML("this doesn't look like html")

        data = resp.read(262144)
        if info.get('Content-Encoding') == 'gzip':
            data = gzip.GzipFile(fileobj=StringIO(data)).read()

        encoding = info.getparam("charset") or getcharset(data)

        title = x_title(html.fromstring(data, parser=html.HTMLParser(encoding=encoding)))
        if not title:
            raise ThereIsNoTitle(u"there's no title in the first 4⁹ bytes")
        title = title[0].text
        if title is None:
            raise MeaninglessTitle(u"title is present but empty")
        title = clean(title)

        if title == "imgur: the simple image sharer": raise MeaninglessTitle("who needs the default imgur title?")
        if title == "Photos" and "core.org.ua" in url: raise MeaninglessTitle(u"рамок снова фотачками хвастается, да?")
        elif title.lower() in url.lower(): raise MeaninglessTitle("title text is contained within the url")
        self.shortargs = self.longargs = (title,)

    shorttemplate = longtemplate = "{!q:m}"


import json, isodate, datetime

# http://www.youtube.com/watch?v=y71vHIdv5IM
# http://youtu.be/y71vHIdv5IM
# http://y2u.be/y71vHIdv5IM


re_youtube = re.compile(r"(?:youtube.com/watch\?(?:\S+?&)?v=|y(?:out|2)u.be/)([A-z0-9_-]+)")
youtube_api_url = u"https://www.googleapis.com/youtube/v3/videos?id={id}&key={key}&part=snippet,contentDetails,statistics&fields=items(id,snippet(title,localized(description),publishedAt),statistics(viewCount,likeCount,dislikeCount),contentDetails(duration))"

class Youtube(object):
    def __init__(self, url):
        if youtube_key is None: raise
        id = re_youtube.search(url).group(1)
        data = json.load(urllib2.urlopen(youtube_api_url.format(id=id, key=youtube_key)))["items"][0]
        title = data["snippet"]["title"]
        try: description = data["snippet"]["localized"]["description"]
        except: description = ""
        try:
            likes = data["statistics"]["likeCount"]
            dislikes = data["statistics"]["dislikeCount"]
            rating = num_to_km(int(likes)) + "/" + num_to_km(int(dislikes))
        except Exception as e:
            rating = u"—"
        viewcount = int(data["statistics"].get("viewCount", 0))
        viewcount = num_to_km(viewcount)
        try:
            duration = data["contentDetails"]["duration"]
            duration = isodate.parse_duration(duration)
            duration = u"∞" if duration == datetime.timedelta(0) else s_to_ms(duration.total_seconds())
        except Exception as e:
            duration = u"∞"


        date = datetime.datetime.strptime(data["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%S.000Z")
        date = date_to_readabledate(date)

        self.shortargs = (title, duration, rating, viewcount, date[0], date[1])
        if description: self.longargs = (title, duration, rating, viewcount, date[0], date[1], clean(description))
        else: self.longtemplate, self.longargs = self.shorttemplate, self.shortargs
    shorttemplate = "{!q:m} ({}, {}, {}, {!t}{})"
    longtemplate = "{!q:m} ({}, {}, {}, {!t}{}): {:250R}"

def s_to_ms(s):
    m, s = divmod(s, 60)
    if m: return "%dm%ds" % (m, s)
    else: return "%ds" % s

def num_to_km(n):
    if n > 1000000:
        return "{:.0f}m".format(n / 1000000.0)
    elif n > 1000:
        return "{:.0f}k".format(n / 1000.0)
    else:
        return str(n)

def date_to_readabledate(then):
    now = datetime.datetime.utcnow()
    days = (now.date() - then.date()).days
    if days > 31:
        return "", then.strftime("%d.%m.%y")
    elif days == 0:
        return u"today at ", then.strftime("%H:%M") + "Z"
    elif days == 1:
        return u"yesterday at ", then.strftime("%H:%M") + "Z"
    else:
        return days, u" days ago"