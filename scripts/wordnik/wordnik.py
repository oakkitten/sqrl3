#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from wordnik import swagger, WordApi
from ...constants import ResultNotFound
from ...utils import clean
import re


def initialize(key):
    """ initialize wordnik api using given key """
    global api
    if api is None:
        client = swagger.ApiClient(key, "http://api.wordnik.com/v4")
        api = WordApi.WordApi(client)


def _repfunc(m):
    word = m.group(1)
    return replacements.get(word, word) + "."


def definition(term):
    """ get definition for given term. raises ResultNotFound """
    defs = api.getDefinitions(term)
    if not defs:
        raise ResultNotFound(u"couldn't find the word in wordnik")

    # strip part of speech data from entries where it gets repeated
    # replace certain terms with shorter equivalents
    # clean
    prev_pos = 1234
    for d in defs:
        pos = d.partOfSpeech.strip()
        d.pos = None if prev_pos == pos else pos_replacements.get(pos, pos)
        prev_pos = pos

        d.text = re.sub(r'^([A-Z][a-z]+|Computer Science) (?=  [A-Z])', _repfunc, d.text)
        d.text = clean(d.text)

    # output
    return defs[0].word + ": " + " ".join((u"({pos}) {n}) {t}" if d.pos else u"{n}) {t}")
                                          .format(pos=d.pos, n=n, t=d.text)
                                          for n, d in enumerate(defs))


def suggestions(term):
    """ return a list of suggestions for given term. raises ResultNotFound """
    word = api.getWord(term)
    sugs = word.suggestions
    if type(sugs) is not list or len(sugs) < 1:
        raise ResultNotFound(u"couldn't find suggestions in wordnik")
    return sugs


replacements = {'Informal': "inf",
                'Slang': 'sl',
                'Nautical': 'naut',
                'Obsolete': 'obs',
                'Sports': 'sp',
                'Computer Science': 'comp',
                'Electronics': 'el',
                'Law': 'law',
                'Linguistics': 'ling'}


pos_replacements = {'noun': 'n',
                    'verb': 'v',
                    'verb-intransitive': 'vi',
                    'verb-transitive': 'vt',
                    'adjective': 'adj',
                    'adverb': 'adv',
                    'pronoun': 'pron',
                    'preposition': 'prep',
                    'conjunction': 'conj',
                    'interjection': 'int'}