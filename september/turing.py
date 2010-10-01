#!/usr/bin/env python
#
# Turing Machine over HTTP
# Copyright 2010 Brendan Berg
#
# Licenced under the MIT license
# http://www.opensource.org/licenses/mit-license.html
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

import re
import tornado.web
import tornado.ioloop
import tornado.httpserver

from optparse import OptionParser

class Transition(object):
	match = None
	replacement = None
	direction = None
	successorState = None
	
	def __init__(self, match, replacement, direction, successorState, initial=None):
		directions = {'<': -1, '>': 1}
		self.match = match
		self.replacement = replacement
		self.direction = directions[direction]
		self.successorState = successorState
	
class Machine(object):
	didHalt = False
	
	def __init__(self, defn):
		# Build a machine for a given definition
		self.currentState = defn.get('currentState', None)
		self.position = defn.get('position', 0)
		self.tape = defn.get('tape', '')
		
		table = { None: [] }
		
		for tr in defn.get('transitions', []):
			table[tr['initial']] = table.get(tr['initial'], [])
			table[tr['initial']].append(Transition(**tr))
		
		self.transitionTable = table
	
	def step(self):
		transitions = self.transitionTable.get(self.currentState, [])
		trs = filter(lambda x: x.match == self.tape[self.position], transitions)
		
		if len(trs) > 0:
			tr = trs[0]
			self.tape = self.tape[:self.position] + tr.replacement + self.tape[self.position + 1:]
			self.position += tr.direction
			self.currentState = tr.successorState
		else:
			self.didHalt = True
		
		if self.position >= len(self.tape):
			self.position = len(self.tape) - 1
			self.didHalt = True
	
	def __str__(self):
		index = self.position
		tape = self.tape
		positionedTape = tape[:index] + "|" + tape[index] + "|" + tape[index + 1:]
		
		transitions = []
		directions = {1: '>', -1: '<'}
		format = '%s(%s%s)%s%s'
		
		for name, trs in self.transitionTable.items():
			for tr in trs:
				data = (name, tr.match, tr.replacement, directions[tr.direction], tr.successorState)
				transitions.append(format % data)
		
		return "%s/%s/%s" % (';'.join(transitions), self.currentState, positionedTape)

class Application(tornado.web.Application):
	def __init__(self):
		# http://hostname/transition-table/current-state/tape[x]head
		# http://hostname/a[ll]>a;a[oo]>b;b[oo]>c;.../a/loooooop
		handlers = [
			(r'/([^/]+)/([^/]+)/(.*)', MachineHandler)
		]
		tornado.web.Application.__init__(self, handlers)
	
	@staticmethod
	def main():
		parser = OptionParser()
		parser.add_option('-p', '--port', 
			dest='port',
			help='run on specified PORT',
			metavar='port'
		)
		
		(opts, args) = parser.parse_args()
		
		server = tornado.httpserver.HTTPServer(Application())
		server.listen(opts.port or 8080)
		tornado.ioloop.IOLoop.instance().start()

class MachineHandler(tornado.web.RequestHandler):
	def transitionScanner(self, string):
		transitions = string.split(';')
		scanner = re.compile(r'(?P<initial>.+)\((?P<match>.)(?P<replacement>.{0,1})\)(?P<direction>[<>])(?P<successorState>.+)')
		return [scanner.match(x).groupdict() for x in transitions if scanner.match(x)]
	
	def tapeScanner(self, string):
		tapeScanner = re.compile(r'^([^|]*)\|(.)\|(.*)$')
		tapeMatch = tapeScanner.match(string)
		
		if not tapeMatch:
			return {
				'string': string,
				'position': 0
			}
		
		tapePieces = tapeMatch.groups()
		
		return {
			'string': ''.join(tapePieces),
			'position': len(tapePieces[0])
		}
		
	def get(self, transitions, state, tape):
		transitionList = self.transitionScanner(transitions)
		tape = self.tapeScanner(tape)
		
		properties = {
			'transitions': transitionList,
			'currentState': state,
			'tape': tape['string'],
			'position': tape['position']
		}
		
		machine = Machine(properties)
		machine.step()
		
		template = '%s://%s/%s'
		data = (self.request.protocol, self.request.host, machine)
		
		if not machine.didHalt:
			self.set_header("Location", template % data)
			self.set_status(302)
		
		return self.write(str(machine))

if __name__ == "__main__":
	Application.main()