#!/usr/bin/python

# cdg2text - cdgtools: CDG to textual representation

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
# cdg2text is a debugging tool for converting your binary .cdg files to
# a textual representation.


# REQUIREMENTS
#
# cdg2text requires the following to be installed on your system:
# . Python (www.python.org)


# USAGE INSTRUCTIONS
#
# To convert a CDG to text, pass the CDG filename/path on the command line:
# 		python cdg2text.py theboxer.cdg
#
# You can pipe the output from cdg2text to a text file if you wish to save
# the results:
#       python cdg2text.py theboxer.cdg > theboxer.txt


import struct, sys, os


# CDG Command Code
CDG_COMMAND 				= 0x09

# CDG Instruction Codes
CDG_INST_MEMORY_PRESET		= 1
CDG_INST_BORDER_PRESET		= 2
CDG_INST_TILE_BLOCK			= 6
CDG_INST_SCROLL_PRESET		= 20
CDG_INST_SCROLL_COPY		= 24
CDG_INST_DEF_TRANSP_COL		= 28
CDG_INST_LOAD_COL_TBL_0_7	= 30
CDG_INST_LOAD_COL_TBL_8_15	= 31
CDG_INST_TILE_BLOCK_XOR		= 38

# Bitmask for all CDG fields
CDG_MASK 					= 0x3F


# cdgPlayer Class
class cdgPlayer:
	# Initialise the player instace
	def __init__(self, cdgFileName):
		self.FileName = cdgFileName

		# Check the CDG file exists
		if not os.path.isfile(self.FileName):
			ErrorString = "No such file: " + self.FileName
			self.ErrorNotifyCallback (ErrorString)
			raise NoSuchFile
			return

		self.decode()


	def decode(self):

		# Open the cdg file
		self.cdgFile = open (self.FileName, "rb") 

		# Main processing loop
		while 1:
			packd = self.cdgGetNextPacket()
			if (packd):
				self.cdgPacketProcess (packd)
			else:
				self.cdgFile.close()
				return

	# Decode the CDG commands read from the CDG file
	def cdgPacketProcess (self, packd):
		if (packd['command'] & CDG_MASK) == CDG_COMMAND:
			inst_code = (packd['instruction'] & CDG_MASK)
			if inst_code == CDG_INST_MEMORY_PRESET:
				self.cdgMemoryPreset (packd)
			elif inst_code == CDG_INST_BORDER_PRESET:
				self.cdgBorderPreset (packd)
			elif inst_code == CDG_INST_TILE_BLOCK:
				self.cdgTileBlockCommon (packd, xor = 0)
			elif inst_code == CDG_INST_SCROLL_PRESET:
				self.cdgScrollPreset (packd)
			elif inst_code == CDG_INST_SCROLL_COPY:
				self.cdgScrollCopy (packd)
			elif inst_code == CDG_INST_DEF_TRANSP_COL:
				self.cdgDefineTransparentColour (packd)
			elif inst_code == CDG_INST_LOAD_COL_TBL_0_7:
				self.cdgLoadColourTableCommon (packd, 0)
			elif inst_code == CDG_INST_LOAD_COL_TBL_8_15:
				self.cdgLoadColourTableCommon (packd, 1)
			elif inst_code == CDG_INST_TILE_BLOCK_XOR:
				self.cdgTileBlockCommon (packd, xor = 1)
			else:
				ErrorString = "Unknown command in CDG file: " + str(inst_code)
				print (ErrorString)

	# Read the next CDG command from the file (24 bytes each)
	def cdgGetNextPacket (self):
		packd={}
		packet = self.cdgFile.read(24)
		if (len(packet) == 24):
			packd['command']=struct.unpack('B', packet[0])[0]
			packd['instruction']=struct.unpack('B', packet[1])[0]
			packd['parityQ']=struct.unpack('2B', packet[2:4])[0:2]
			packd['data']=struct.unpack('16B', packet[4:20])[0:16]
			packd['parity']=struct.unpack('4B', packet[20:24])[0:4]
			return packd
		elif (len(packet) > 0):
			print ("Didnt read 24 bytes")
			return None

	# Set the preset colour
	def cdgMemoryPreset (self, packd):
		colour = packd['data'][0] & 0x0F
		repeat = packd['data'][1] & 0x0F
		print ("cdgMemoryPreset [Colour=%d, Repeat=%d]" % (colour, repeat))
		return

	# Set the border colour
	def cdgBorderPreset (self, packd):
		colour = packd['data'][0] & 0x0F
		print ("cdgMemoryPreset [Colour=%d]" % colour)
		return

	# CDG Scroll Command - Set the scrolled in area with a fresh colour
	def cdgScrollPreset (self, packd):
		self.cdgScrollCommon (packd, copy = False)
		return

	# CDG Scroll Command - Wrap the scrolled out area into the opposite side
	def cdgScrollCopy (self, packd):
		self.cdgScrollCommon (packd, copy = True)
		return

	# Common function to handle the actual pixel scroll for Copy and Preset
	def cdgScrollCommon (self, packd, copy):

		# Decode the scroll command parameters
		data_block = packd['data']
		colour = data_block[0] & 0x0F
		hScroll = data_block[1] & 0x3F
		vScroll = data_block[2] & 0x3F
		hSCmd = (hScroll & 0x30) >> 4
		hOffset = (hScroll & 0x07)
		vSCmd = (vScroll & 0x30) >> 4
		vOffset = (vScroll & 0x0F)

		if (copy == True):
			typeStr = "cdgScrollCopy"
		else:
			typeStr = "cdgScrollPreset"

		print ("%s [colour=%d, hScroll=%d, vScroll=%d]" % (typeStr, colour, hScroll, vScroll))
		return
	
	# Set the colours for a 12x6 tile. The main CDG command for display data
	def cdgTileBlockCommon (self, packd, xor):
		# Decode the command parameters
		data_block = packd['data']
		colour0 = data_block[0] & 0x0F
		colour1 = data_block[1] & 0x0F
		column_index = ((data_block[2] & 0x1F) * 12)
		row_index = ((data_block[3] & 0x3F) * 6)
		
		if (xor == True):
			typeStr = "cdgTileBlockXOR"
		else:
			typeStr = "cdgTileBlockNormal"

		print ("%s [Colour0=%d, Colour1=%d, ColIndex=%d, RowIndex=%d]"
			 	% (typeStr, colour0, colour1, column_index, row_index))
		return

	# Set one of the colour indeces as transparent.
	def cdgDefineTransparentColour (self, packd):
		data_block = packd['data']
		colour = data_block[0] & 0x0F
		print ("cdgDefineTransparentColour [Colour=%d]" % colour)
		return

	# Load the RGB value for colours 0..7 or 8..15 in the lookup table
	def cdgLoadColourTableCommon (self, packd, table):
		if table == 0:
			colourTableStart = 0
			print ("cdgLoadColourTable0..7")
		else:
			colourTableStart = 8
			print ("cdgLoadColourTable8..15")
		for i in range(8):
			colourEntry = ((packd['data'][2 * i] & CDG_MASK) << 8)
			colourEntry = colourEntry + (packd['data'][(2 * i) + 1] & CDG_MASK)
			colourEntry = ((colourEntry & 0x3F00) >> 2) | (colourEntry & 0x003F)
			print ("  Colour %d = 0x%X" % ((i + colourTableStart), colourEntry))
		return

# Print out some instructions on error
def usage():
    print "Usage:  %s <CDG filename>" % os.path.basename(sys.argv[0])

# Can be called from the command line with the CDG filepath as parameter
def main():
	args = sys.argv[1:]
	if (len(sys.argv) != 2) or ("-h" in args) or ("--help" in args):
		usage()
		sys.exit(2)
	player = cdgPlayer(sys.argv[1])

if __name__ == "__main__":
    sys.exit(main())
