#!/usr/bin/python
# -*- coding: utf-8 -*-

from sqrl3.constants import ResultNotFound
from sqrl3.utils import clean, num_to_km
from sqrl3.web import opener
from urllib2 import quote
import json


def urbandictionary(text):
    """
    returns definition from urban dictionary
    input: u"word"
    returns: "word", "definition", "example", "123", "23"
    raises: ResultNotFound, *
    """

    # base url:
    #     http://api.urbandictionary.com/v0/define?term=%s
    #
    # json returns:
    #     {"list": [
    #       {"author": "The Ugly One",
    #        "current_vote": "",
    #        "defid": 531350,
    #        "definition": "One plus One can equal Three without protection.",
    #        "example": u"Who says math doesn't apply to real life?",
    #        "permalink": "http://113.urbanup.com/531350",
    #        "thumbs_down": 36,
    #        "thumbs_up": 201,
    #        "word": "1+1=3"},
    #        ...],
    #     "result_type": u"exact",
    #     "sounds": [],
    #     "tags": []}
    #
    # or
    #     {"list": [],
    #     "result_type": "no_results",
    #     "sounds": [],
    #     "tags": []}

    text = unicode(text).encode("utf-8")
    data = opener.open("http://api.urbandictionary.com/v0/define?term=%s" % quote(text)).read()
    data = json.loads(data)
    try:
        li = data["list"][0]
        return clean(li["word"]), clean(li["definition"]), clean(li["example"]), \
            num_to_km(li["thumbs_up"]), num_to_km(li["thumbs_down"])
    except IndexError:
        raise ResultNotFound("word not found in urbandictionary")
