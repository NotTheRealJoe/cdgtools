#!/usr/bin/python

# cdgcddb - cdgtools: CDDB module

# Copyright (C) 2005  Kelvin Lawson (kelvinl@users.sf.net)
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


# OVERVIEW
#
# cdgcddb is used for looking up the track names of a CD in CDDB.
# It was designed to provide cdgtools with an LGPL-licensed CDDB
# module, but is not a karaoke-specific tool - it can be used to
# query CDDB for any standard CD.
#
# cdgcddb is part of the cdgtools suite of CD+G karaoke software.
# See http://www.kibosh.org/cdgtools/ for more details.


# Required for the http/cddb protocol
import urllib

# Required for getting the user/hostname needed for CDDB
import getpass, socket


CDDB_SERVER		= "http://freedb.freedb.org/~cddb/cddb.cgi"
CLIENT_NAME		= "cdgtools"
CLIENT_VER		= "0.1"
CLIENT_PROTO	= 3			# Don't support multiple exact matches


def cddbSum ( n ):
	ret = 0
	while (n > 0):
		ret = ret + (n % 10)
		n = n / 10
	return (ret)

def cddbQuery ( trackStartMins, trackStartSecs, trackStartFrames, leadoutStartMin, leadoutStartSec ):
	n = 0
	tot_trks = len (trackStartMins)
	totalSecs = (leadoutStartMin * 60) + leadoutStartSec
	infoDict = {}
	returnDict = None
	
	# Get the user/host names for CDDB
	username = getpass.getuser()
	hostname = socket.gethostname()

	# Create the CDDB disc ID
	for i in range(tot_trks):
		n = n + cddbSum((trackStartMins[i] * 60) + trackStartSecs[i])
	t = ((leadoutStartMin * 60) + leadoutStartSec) - ((trackStartMins[0] * 60) + trackStartSecs[0])
	discId = ((long(n) % 0xff) << 24 | long(t) << 8 | long(tot_trks))

	# Build the CDDB query string
	queryString = "%08x+%d" % (discId, tot_trks)
	for i in range(tot_trks):
		frameOffset = (((trackStartMins[i] * 60) + trackStartSecs[i]) * 75) + trackStartFrames[i]
		queryString = queryString + ("+%s" % frameOffset)
	queryString = queryString + ("+%d" % totalSecs)

	fullString = ("%s?cmd=cddb+query+%s&hello=%s+%s+%s+%s&proto=%d" %
				(CDDB_SERVER, queryString, username, hostname, CLIENT_NAME, CLIENT_VER, CLIENT_PROTO))

	# The hello handshake
	queryResponse = urllib.urlopen (fullString)
	responseData = queryResponse.readlines()
	response = responseData[0].split()
	
	# Check the error code
	matchFound = False
	if response[0] == "200":
		# Match found. Build the title string from the response word list
		dtitle = ""
		for token in response[3:]:
			dtitle = dtitle + ("%s " % token)
		dtitle.strip ("\r\n")
		# Store the details in the dictionary
		infoDict['DTITLE'] = dtitle
		infoDict['CATEG'] = response[1]
		infoDict['DISCID'] = response[2]
		infoString = "CDDB match: %s" % dtitle
		# Notify later sections that we found a match
		matchFound = True
	elif response[0] == "211":
		infoString = "211: Inexact matches found in CDDB"
	elif response[0] == "202":
		infoString = "202: No match found in CDDB"
	elif response[0] == "403":
		infoString = "403: CDDB database entry is corrupt"
	elif response[0] == "409":
		infoString = "409: No CDDB handshake"
	else:
		infoString = "Uknown CDDB response (%s)" % response[0]
		
	# Do a CDDB read if a match was found
	if matchFound == True:
		# Perform a CDDB read operation
		fullString = ("%s?cmd=cddb+read+%s+%s&hello=%s+%s+%s+%s&proto=%d" %
					(CDDB_SERVER, infoDict['CATEG'], infoDict['DISCID'], 
					username, hostname, CLIENT_NAME, CLIENT_VER, CLIENT_PROTO))
		readResponse = urllib.urlopen (fullString)
		responseData = readResponse.readlines()
		response = responseData[0].split()

		# Parse the response for a match/errors
		if response[0] == "210":
			# Match found. Fill the dictionary with the returned details
			for line in responseData[1:]:
				# Read all non-comment (#) lines out and stop at the terminator (.)
				if line[0] == '.':
					break
				elif line[0] != '#':
					split_string = line.split('=')
					infoDict[split_string[0]] = split_string[1].strip("\r\n")
			# Got a valid dictionary to return now
			returnDict = infoDict
			infoString = "%s" % infoDict['DTITLE']
		elif response[0] == "401":
			infoString = "401: Specified CDDB entry not found"
		elif response[0] == "402":
			infoString = "402: CDDB server error"
		elif response[0] == "403":
			infoString = "403: CDDB database entry is corrupt"
		elif response[0] == "409":
			infoString = "409: No CDDB handshake"
		else:
			infoString = "Uknown CDDB response (%s)" % response[0]

	# Return the info string, and (if a match was found) the database dictionary
	return (infoString, returnDict)

	
