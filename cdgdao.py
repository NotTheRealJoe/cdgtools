# cdgdao - cdgtools: cdrdao output parser

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
# cdgdao is part of the cdgtools suite of CD+G karaoke software.
#
# This module can be used to parse the TOC files output after
# ripping a CD+G disk using cdrdao. It provides the rest of 
# cdgtools with information on the ripped disk, which can
# then be used to rip out the audio and graphic data for
# MP3+G encoding etc.
#
# The CD+G disk should be ripped using the --read-subchan command
# of cdrdao. An example command-line is:
#   cdrdao read-cd --driver generic-mmc-raw --device /dev/cdroms/cdrom0 --read-subchan rw_raw mycd.toc
#
# You can rip in either rw_raw (interleaved) or rw (deinterleaved) modes,
# depending on what modes your CD drive supports.
#
# See cdgrip.py for an example ripping application which utilises
# this module.
#
# For further details see http://www.kibosh.org/cdgtools/


# Take a cdrdao-produced TOC file and return track details etc
def ParseToc (tocfilename):

	trackStartByte = []
	trackSizeBytes  = []
	trackNum = 0
	currBytePos = 0

	# Read entire file into RAM
	tocfile = open (tocfilename, "r")
	tocdata = tocfile.read()	
	tocfile.close()	

	# Get the binfile name from the TOC (assume only one for a rip)
	searchString = "DATAFILE \""
	foundPos = tocdata.find (searchString)
	if (foundPos == -1):
		print ("cdgdao: Error finding binfile name in TOC")
		return (None, None, None, None)
	binfileStartPos = foundPos + len(searchString)
	binfileEndPos = tocdata.find ("\"", binfileStartPos)
	binfilename = tocdata[binfileStartPos:binfileEndPos]

	# Find out from the TOC file if the data is raw and needs deinterleaving
	if (tocdata.find ("RW_RAW") != -1):
		interleaved = True
	else:
		interleaved = False

	# Parse the TOC file, keeping a list of the start 
	# sector and and sector size of each track.
	searchString = "length in bytes: "
	foundPos = tocdata.find (searchString, 0)
	while (foundPos != -1):
		# Get the sector size
		sizeStringStartPos = foundPos + len(searchString)
		sizeStringEndPos = tocdata.find ("\n", sizeStringStartPos)
		trackSizeString = tocdata[sizeStringStartPos:sizeStringEndPos]
		trackStartByte.append (currBytePos)
		trackSizeBytes.append (int(trackSizeString))
		currBytePos = currBytePos + trackSizeBytes[trackNum]

		# Update start position for next search, and search again
		trackNum = trackNum + 1
		foundPos = tocdata.find (searchString, sizeStringEndPos)

	# Return the data to the caller
	return (binfilename, interleaved, trackStartByte, trackSizeBytes)


