#!/usr/bin/python
# -*- coding: utf-8 -*-

from ...constants import ResultNotFound
from .wordnik import Wordnik
import argparse

parser = argparse.ArgumentParser(description="wordnik fetcher", prog="wordnik")
parser.add_argument('-k', '--key', action='store', dest='key', metavar='key', help='wordnik api key', required=True)
parser.add_argument('expression', action='store', nargs=argparse.REMAINDER, metavar='expression')
args = parser.parse_args()
key = args.key
word = " ".join(args.expression)

w = Wordnik(args.key)
try: print w.definition(word)
except ResultNotFound: print "definition not found"

try: print "suggestions:", ', '.join(w.suggestions(word))
except ResultNotFound: print "no suggestions"

