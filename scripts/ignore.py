#!/usr/bin/python
# -*- coding: utf-8 -*-

""" plugin description """

from sqrl3.script import onprivmsg, onload, onunload, HaltMessage
from collections import defaultdict
from gevent import spawn_later

############################################################ admin

@onload
def load(self):
    self.ignore = defaultdict(int)

@onprivmsg(block=True)
def ignore(self, msg):
    # if the message is a bot command,
    # increase the number of commands by sender
    # track sender by host
    if msg.command:
        if self.ignore[msg.host] < 0:
            raise HaltMessage
        else:
            if self.ignore[msg.host] > 5 - 1:
                # turn ignore on
                # schedule resetting
                def reset_counter():
                    del self.ignore[msg.host]
                msg.action("turns down the volume of {} a bit", msg.nick)
                self.ignore[msg.host] = -1
                self.group.add(spawn_later(60 * 5, reset_counter))
                raise HaltMessage
            else:
                # increase counter
                # schedule removing
                def decrease_counter():
                    self.ignore[msg.host] -= 1
                self.ignore[msg.host] += 1
                self.group.add(spawn_later(60, decrease_counter))
