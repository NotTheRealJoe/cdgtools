#!/usr/bin/python

# cdgtools - cdgtools: Common library module and GUI starter
#
# Copyright (C) 2009  Kelvin Lawson (kelvinl@users.sf.net)
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
# cdgtools is a suite of tools for ripping and handling CD+G
# karaoke disks and MP3+G files.
#
# This module contains some simple settings and functions which are
# shared amongst the various cdgtools programs. It can also be used
# to start the GUI (cdggui.py).
#
# See http://www.kibosh.org/cdgtools/ for more details.


import sys

# Common version string for all cdgtools modules
VERSION_STRING = "0.3.2"


# Compute CD track MSFs from their start offsets in bytes.
def ComputeMSF (byteOffset):
	# Include the 150 frame (2 second) pregap
	totalframes = (byteOffset / 2448) + 150
	totalsecs =  totalframes / 75
	# Calculate the MSF
	minutes = totalsecs / 60
	seconds = totalsecs % 60
	frames = totalframes % 75
	return (minutes, seconds, frames)


# If called from the command line, starts the GUI
if __name__ == "__main__":
	import cdggui
	sys.exit(cdggui.StartGUI())
