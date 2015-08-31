#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from .urbandictionary import urbandictionary


query = ' '.join(sys.argv[1:])
print u"{0}: {1} ({3}/{4}) {2}".format(*urbandictionary(query))
