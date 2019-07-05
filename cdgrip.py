#!/usr/bin/python

# cdgrip - cdgtools: CD+G Ripper

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
# cdgrip is a tool for ripping CD+G disks to the MP3+G format.
#
# CD+G disks should first be ripped using cdrdao, which produces a
# TOC file and a BIN file. You can then pass the TOC file into
# cdgrip, and it will rip out the audio and graphic data. The audio
# is encoded to an mp3 file, and the graphic data is saved as a .cdg
# file.
#
# cdgrip can also look for track names via CDDB, and use these for
# the resultant mp3 and cdg filenames.
# 
# Note that not all CD/DVD drives are capable of handling CD+G disks.
# You should check whether your drive supports reading the subchannel
# R-W data. Some drives can only support reading interleaved (raw)
# R-W data - this is fine for cdgrip. It performs a software
# deinterleave for you.
#
# Because cdgrip is written in Python, it can be used on many
# operating systems. If cdrdao has been ported to your operating
# system then you should be able to use cdgrip. See
# http://cdrdao.sourceforge.net/ for more details.
#
# cdgrip is part of the cdgtools suite of CD+G karaoke software.
# See http://www.kibosh.org/cdgtools/ for more details.


# REQUIREMENTS
#
# cdgrip requires the following to be installed on your system:
# . Python (http://www.python.org)
# . cdrdao (http://cdrdao.sourceforge.net)
# . lame (http://lame.sourceforge.net)
#
# If you wish to use an alternative encoder to lame, you can
# change the command-string in the cdgrip() function below 
# (see lame_string). If you would like to see native support
# for your favourite encoder, or make it configurable from
# the command-line, let us know.
#
# With some small changes it is also possible to use bin files
# generated by CD rippers other than cdrdao, such as readcd
# from the cdrecord package. If you can't use cdrdao or would
# prefer to use an alternative ripper, let us know.


# QUICK START
#
# To start using cdgrip immediately, try the following from the 
# command-line (replacing the --device option by the path to your
# CD device):
#
#  $ cdrdao read-cd --driver generic-mmc-raw --device /dev/cdroms/cdrom0 --read-subchan rw_raw mycd.toc
#  $ python cdgrip.py --with-cddb --delete-bin-toc mycd.toc
#
# You may need to use a different --driver option or --read-subchan mode
# to cdrdao depending on your CD device. For more in depth details, see
# the usage instructions below.


# USAGE INSTRUCTIONS
#
# cdgrip does not perform the actual ripping from CD drives - cdrdao
# is used for that, and is available on most systems. Before calling
# cdgrip, you should use cdrdao to rip your CD+G disk. This generates
# a BIN file and a TOC file, which you can then pass into cdgrip to 
# do the mp3+g encoding.
#
# The CD+G disk should be ripped using the --read-subchan command
# of cdrdao. An example command-line is:
#   cdrdao read-cd --driver generic-mmc-raw --device /dev/cdroms/cdrom0 --read-subchan rw_raw mycd.toc
#
# You should replace the device by the correct path to your CD drive.
# You may also need to use a different driver, depending on your drive. 
# See the cdrdao manpage for more details on the driver options.
#
# You can rip in either rw_raw (interleaved) or rw (deinterleaved) modes,
# depending on what modes your CD drive supports. If your drive only
# supports reading in rw (deinterleaved) mode, you can replace
# "--read-subchan rw_raw" with "--read-subchan rw". Note that no
# deinterleaved mode drives were available for testing, please let us
# know what success you have with this mode.
#
# Once the cdrdao rip is complete, you should be left with a toc file
# (e.g. mycd.toc) and a bin file (data.bin by default). You can now
# use cdgrip to do the MP3+G encoding:
#
#   python cdgrip.py mycd.toc
#
# This will rip the entire CD, generating a full set of .mp3 and .cdg
# files for you. The toc and bin files are left on disk by default.
# If you would like cdgrip to delete them for you when it is finished,
# add the --delete-bin-toc option:
#
#   python cdgrip.py --delete-bin-toc mycd.toc
#
# By default cdgrip uses generic track names (track01.mp3, track02.mp3 etc).
# To attempt to get actual track names using a CDDB connection, add
# the --with-cddb option. e.g.:
#
#   python cdgrip.py --with-cddb mycd.toc
#
# If a match is found in CDDB then your .mp3 and .cdg files will use
# these names instead.


# IMPLEMENTATION DETAILS
#
# cdgtools provides a set of modules which can be used together with
# CD ripping software to encode a CD+G disk to MP3+G. The ripping modules
# are as follows:
#
# . cdgdao   - Parses the TOC files created by cdrdao to get track 
#              information for cdrdao BIN files.
# . cdgparse - Parses ripped BIN files, to generate raw audio PCM files
#              and CDG binary files. Also deinterleaves if the rip was
#              done in raw mode.
# . cdgrip   - Command-line application which utilises the above two
#              modules to do the full MP3+G encode process, including
#              getting track details from CDDB if available.
#
# An external utility (lame) is used to do the PCM to MP3 encoding.
# This can easily be replaced by other mp3 encoders or encoders to
# other formats such as ogg.
#
# Other CD ripping software can be supported if they generate bin
# files in the same format (2352 bytes audio, followed by 96 bytes
# subchannel data). To add support for other software, you should
# implement a module similar to cdgdao which provides cdgrip with
# the track start and size details. You should also establish
# whether the subchannel data in the bin file needs to be 
# deinterleaved or not (it does if it was read using raw mode).


# Standard Python and local imports
import sys, os, getopt
import cdgtools, cdgdao, cdgparse, cdgcddb


# Constants
TITLE_STRING = " cdgrip %s / Kelvin Lawson 2005" % cdgtools.VERSION_STRING
DELIMITER = ("-----------------------------------------------------------")



def cdgrip(tocfilename, delete_bin_toc=False, with_cddb=False, verbose=False):

	# Parse the TOC file to get the bin file and track details
	binfilename, interleaved, startBytes, trackSizeBytes = cdgdao.ParseToc (tocfilename)

	# Output details to the console
	print (DELIMITER)
	print (TITLE_STRING)
	print (DELIMITER)
	print ("-> Binfile: %s" % binfilename)

	# Attempt to get track names from CDDB
	trackStartMins = []
	trackStartSecs = []
	trackStartFrames = []
	for track in startBytes:
		mins, secs, frames = cdgtools.ComputeMSF (track)
		trackStartMins.append(mins)
		trackStartSecs.append(secs)
		trackStartFrames.append(frames)
	# Guess the leadout start based on the start offset and size of the last track
	numTracks = len(trackStartMins)
	leadoutStartByte = startBytes[numTracks - 1] + trackSizeBytes[numTracks - 1]
	leadoutMins, leadoutSecs, leadoutFrames = cdgtools.ComputeMSF (leadoutStartByte)

	# Create generic track names in case no match found, or CDDB is disabled			
	trackNames = []
	for track in range(numTracks):
		trackNames.append ("track%.02d" % (track + 1))

	# Do the CDDB query if requested
	if (with_cddb == True):

		print (DELIMITER)
		print ("-> Attempting to get tracklist from CDDB")
		resultString, cddbDict = cdgcddb.cddbQuery (trackStartMins, trackStartSecs, 
													trackStartFrames, leadoutMins, leadoutSecs )
		print ("-> CDDB result: %s" % resultString)

		# If a match was found, fill the track list with CDDB track names
		if cddbDict != None:
			trackNames = []
			for i in range(numTracks):
				# Create the track name, remove any slashes
				trackname = "%.02d - %s" % ((i + 1), cddbDict['TTITLE' + `i`])
				trackname = trackname.replace ("/", "-")
				trackname = trackname.replace ("\\", "-")
				trackNames.append(trackname)
				print ("-> CDDB track info: %s" % trackname)
			# Otherwise (no CDDB match found) use generic track names

	# Convert the audio and subchannel data for each track to .mp3 and .cdg files
	for track in range(numTracks):
		print (DELIMITER)
		print ("-> Starting: %s" % trackNames[track])
		if verbose == True:
			print ("-> Track start byte = %d, Track Size = %d"
					% (startBytes[track], trackSizeBytes[track]))

		# Rip the audio to a raw PCM file
		print ("-> Ripping audio")
		pcmdata = cdgparse.bin2pcm (binfilename, startBytes[track], trackSizeBytes[track])
		cdgparse.pcmWriteToFile ("temp.pcm", pcmdata)
		
		# Encode with lame
		print ("-> Encoding audio to mp3")
		mp3name = "%s.mp3" % trackNames[track]
		# Quote any songnames with spaces in before calling lame
		if mp3name.find(" ") != -1:
			mp3name = "\"%s\"" % mp3name
		lame_string = "lame -r --silent --cbr --big-endian temp.pcm %s" % mp3name
		os.system (lame_string)

		print ("-> Ripping CD+G subchannel data")
		cdgdata = cdgparse.bin2cdg (binfilename, startBytes[track], trackSizeBytes[track])

		# Deinterleave if the data is in raw format
		if (interleaved):
			print ("-> Deinterleaving raw CD+G data")
			cdgdata = cdgparse.Deinterleave (cdgdata)

		# Write the finished CDG data out to a file
		cdgname = "%s.cdg" % trackNames[track]
		print ("-> Finished: %s" % trackNames[track])
		cdgparse.cdgWriteToFile (cdgname, cdgdata)

	# Delete the temporary PCM audio file
	os.unlink ("temp.pcm")

	# Delete the TOC and BIN file if requested
	print (DELIMITER)
	if delete_bin_toc == True:
		print ("-> Deleting the cdrdao output files (%s, %s)" % (tocfilename, binfilename))
		os.unlink(tocfilename)
		os.unlink(binfilename)
	else:
		print ("-> Not deleting the cdrdao output files (%s, %s)" % (tocfilename, binfilename))
		print ("-> Use --delete-bin-toc to delete them after ripping")

	# Finished
	print (DELIMITER)
	print ("-> CD+G rip complete")
	print (DELIMITER)

	return


# Usage instructions
def usage():
	print (TITLE_STRING)
	print ("")
	print ("Usage:  %s [options] tocfilename" % os.path.basename(sys.argv[0]))
	print ("")
	print ("Options:")
	print ("")
	print ("")
	print ("  -v                        :    Verbose mode")
	print ("")
	print ("  --delete-bin-toc          :    Delete the cdrdao-ripped bin and toc")
	print ("                                 files when finished")
	print ("")
	print ("  --with-cddb               :    Attempt to get track names from CDDB")
	print ("")
	print ("  --help                    :    Display this message")
	print ("")

	return


# Can be called from the command line with the TOC filename as parameter (plus options)
# This just gathers the options together and calls cdgrip()
def main():
	
	# Get the options out
	try:
		opts, args = getopt.getopt(sys.argv[1:], "hv", ["delete-bin-toc", "help", "with-cddb"])
	except getopt.GetoptError:
		usage()
 		sys.exit(2)

	# Check the user passed in the tocfile
	if len(args) != 1:
		usage()
		sys.exit(2)
	else:
		tocfile = args[0]

	# Default settings
	with_cddb = False
	delete_bin_toc = False
	verbose = False

	# Parse the command-line options   
	for opt, arg in opts:
 		if opt in ("-h", "--help"):
			usage()
			sys.exit()
		if opt == "-v":
			verbose = True
		if opt in ("--with-cddb"):
			with_cddb = True
		if opt in ("--delete-bin-toc"):
			delete_bin_toc = True

	# Do the rip
	cdgrip(tocfile, delete_bin_toc, with_cddb, verbose)

	return

if __name__ == "__main__":
    sys.exit(main())
