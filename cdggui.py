#!/usr/bin/python

# cdggui - cdgtools: CD+G Ripper GUI
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
# cdggui is a GUI frontend for cdgtools. It is used for ripping CD+G
# disks to the MP3+G format.
#
# CD+G disks should first be ripped using cdrdao, which produces a
# TOC file and a BIN file. You can then open the TOC file in cdggui
# and encode to mp3 and cdg files.
#
# Track names can be retrieved from CDDB (if available in the
# database) or edited by hand in the GUI's tracklist. 
#
# cdggui is part of the cdgtools suite of CD+G karaoke software.
# See http://www.kibosh.org/cdgtools/ for more details.


# REQUIREMENTS
#
# cdggui requires the following to be installed on your system:
# . Python (http://www.python.org)
# . wxpython (http://www.wxpython.org)
# . cdrdao (http://cdrdao.sourceforge.net)
# . lame (http://lame.sourceforge.net)


# USAGE INSTRUCTIONS
#
# cdggui does not perform the actual ripping from CD drives - cdrdao
# is used for that, and is available on most systems. Before starting
# cdggui, you should use cdrdao to rip your CD+G disk. This generates
# a BIN file and a TOC file, which you can then open in cdggui to 
# do the mp3+g encoding.
#
# See cdgrip.py for instructions on using cdrdao to rip CD+G disks.
#
# Once the cdrdao rip is complete, you should be left with a toc file
# (e.g. mycd.toc) and a bin file (data.bin by default). You can now
# use cdggui to do the MP3+G encoding:
#
#   python cdggui.py
#
# This starts the GUI and presents the user with a blank tracklist.
# You can then open your generated TOC file using the File menu.
#
# On opening the TOC file, cdggui will consult CDDB to check whether
# track names are available there. If so, the tracklist window will
# be populated using the track names from CDDB. If no data is
# available in CDDB, then cdggui will generate a track list with
# generic track names ("track01", "track02" etc).
#
# You can then right-click on tracks in the track list to rename
# the tracks and hence the resultant .mp3 and .cdg filenames.
#
# Once you are happy with your track names, you can right-click a
# track in the track list and encode it to MP3+G. Alternatively you can
# encode the entire CD from the Actions menu.
#
# By default the .mp3/.cdg files will be created in the current
# directory. You can change the destination directory from the 
# Options menu. You can also configure the location of your
# lame encoder program from this menu. If lame is already in
# your system path, however, this is not necessary.
#
# Other configuration options are:
#  * Enable CDDB - Enable/Disable getting track names from CDDB
#  * Delete TOC/BIN - Delete the cdrdao TOC/BIN files when finished encoding


import wx
from threading import *
import cdgtools, cdgdao, cdgparse, cdgcddb
import os, time, sys, types

TITLE_STRING = "cdgtools %s" % cdgtools.VERSION_STRING

DEFAULT_HEIGHT = 420
DEFAULT_WIDTH  = 480

# SettingsStruct used as storage only for settings. The instance
# can be pickled to save all user's settings.
class SettingsStruct:
	def __init__(self, EnableCDDB=True, DeleteTocBin=False, DestDir="", LameLoc=""):
		self.EnableCDDB 	= EnableCDDB		# CDDB enabled
		self.DeleteTocBin 	= DeleteTocBin		# Delete TOC/BIN after encode
		self.DestDir		= DestDir			# Destination directory for MP3+G files
		self.LameLoc		= LameLoc			# Lame executable location

# Define notification event for worker thread completion
EVT_DONE_ID = wx.NewId()


# Generic function for popping up errors
def ErrorPopup (ErrorString):
	wx.MessageBox(ErrorString, "Error", wx.OK | wx.ICON_ERROR)


class TracksPanel (wx.Panel):
	def __init__(self, parent, id, x, y):
		wx.Panel.__init__(self, parent, id)
		self.parent = parent
		
		# Create the playlist control
		self.TracksId = wx.NewId()
		self.TrackList = wx.ListCtrl(self, self.TracksId,
									style=wx.LC_REPORT | wx.LC_SINGLE_SEL |
									wx.SUNKEN_BORDER | wx.LC_EDIT_LABELS)
		self.TrackList.InsertColumn (0, "Track list", width=DEFAULT_WIDTH)
		self.TrackList.Show(True)

		# Create the status bar
		self.StatusBar = wx.StatusBar(self, -1)
		self.StatusBar.SetStatusText ("No rip loaded")

		# Create a sizer for the tree view and status bar
		self.VertSizer = wx.BoxSizer(wx.VERTICAL)
		self.VertSizer.Add(self.TrackList, 1, wx.EXPAND, 0)
		self.VertSizer.Add(self.StatusBar, 0, wx.EXPAND, 0)
		self.SetSizer(self.VertSizer)

		# Create IDs for popup menu
		self.menuRenameId = wx.NewId()
		self.menuEncodeId = wx.NewId()

		# Add handlers for right-click in the listbox
		wx.EVT_LIST_ITEM_RIGHT_CLICK(self.TrackList, wx.ID_ANY, self.OnRightClick)
		self.RightClickedItemIndex = -1

		# Resize column width to the same as list width (or max title width, which larger)
		wx.EVT_SIZE(self.TrackList, self.onResize)
		self.MaxTitleWidth = 0

		self.Show(True)

	# Handle right-click in the track list (show popup menu).
	def OnRightClick(self, event):
		self.RightClickedItemIndex = event.GetIndex()
		# Doesn't bring up a popup if no items are in the list
		if self.TrackList.GetItemCount() > 0:
			menu = wx.Menu()
			menu.Append( self.menuRenameId, "Rename track" )
			wx.EVT_MENU( menu, self.menuRenameId, self.OnMenuSelection )
			menu.Append( self.menuEncodeId, "Encode track" )
			wx.EVT_MENU( menu, self.menuEncodeId, self.OnMenuSelection )
			self.TrackList.SetItemState(
					self.RightClickedItemIndex,
					wx.LIST_STATE_SELECTED|wx.LIST_STATE_FOCUSED,
					wx.LIST_STATE_SELECTED|wx.LIST_STATE_FOCUSED)
			self.TrackList.PopupMenu( menu, event.GetPoint() )

	# Handle popup menu selection events.
	def OnMenuSelection( self, event ):
		if event.GetId() == self.menuRenameId:
			self.TrackList.EditLabel(self.RightClickedItemIndex)
		elif event.GetId() == self.menuEncodeId:
				self.EncodeTrack(self.RightClickedItemIndex)

	# Encode a single track (right-click)
	def EncodeTrack (self, track_index):
		track_list = [track_index]
		self.parent.DoEncode(track_list)
	
	def InsertItem (self, TrackNum, ItemString):
		# Add the track to the listctrl
		self.TrackList.InsertStringItem(TrackNum, ItemString)
		# Update the max title width, if this one is the largest yet
		if ((len(ItemString) * self.GetCharWidth()) > self.MaxTitleWidth):
			self.MaxTitleWidth = len(ItemString) * self.GetCharWidth()
			self.doResize()

	def GetItemText (self, TrackNum):
		# Return the string associated with this list entry
		return (self.TrackList.GetItemText(TrackNum))

	def GetItemCount (self):
		# Return the number of list entries
		return (self.TrackList.GetItemCount())

	def ClearList (self):
		self.MaxTitleWidth = 0
		for item in range(self.TrackList.GetItemCount()):
			self.TrackList.DeleteItem(0)

	# Resize handler
	def onResize(self, event):
		self.doResize()
		event.Skip()

	# Common handler for SIZE events and our own resize requests
	def doResize(self):
		# Get the listctrl's width
		listWidth = self.TrackList.GetClientSize().width
		# We're showing the vertical scrollbar -> allow for scrollbar width
		# NOTE: on GTK, the scrollbar is included in the client size, but on
		# Windows it is not included
		if wx.Platform != '__WXMSW__':
			if self.TrackList.GetItemCount() > self.TrackList.GetCountPerPage():
				scrollWidth = wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
				listWidth = listWidth - scrollWidth

		# Only one column, set its width to list width, or the longest title if larger
		if self.MaxTitleWidth > listWidth:
			width = self.MaxTitleWidth
		else:
			width = listWidth

		self.TrackList.SetColumnWidth(0, width)


class cdgtoolsWindow(wx.Frame):
	""" Derive a new class of Frame. """
	def __init__(self,parent,id,title):
		wx.Frame.__init__(self,parent,wx.ID_ANY, title, size = (DEFAULT_WIDTH, DEFAULT_HEIGHT),
						style=wx.DEFAULT_FRAME_STYLE|wx.NO_FULL_REPAINT_ON_RESIZE)
		self.Show(True)

		# Load the settings
		self.Settings = SettingsStruct()

		# Create the main panel
		self.TracksPanel = TracksPanel(self, -1, 0, 0)
		self.TracksSizer = wx.BoxSizer(wx.VERTICAL)
		self.TracksSizer.Add(self.TracksPanel, 1, wx.ALL | wx.EXPAND, 5)

		# Create the global sizer
		self.ViewSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.ViewSizer.Add(self.TracksSizer, 1, wx.ALL | wx.EXPAND, 5)

		# Create the main sizer
		self.MainSizer = wx.BoxSizer(wx.VERTICAL)
		self.MainSizer.Add(self.ViewSizer, 1, wx.ALL | wx.EXPAND)
		self.SetAutoLayout(True)
		self.SetSizer(self.MainSizer)
	
		# Create the top menu
		menuBar = wx.MenuBar()

		# Create the file menu
		self.FileMenu = wx.Menu()
		self.idOpen = wx.NewId()
		self.idExit = wx.NewId()
		self.FileMenu.Append(self.idOpen, "&Open TOC file"," Open TOC file")
		self.FileMenu.AppendSeparator()
		self.FileMenu.Append(self.idExit,"E&xit"," Exit")
		menuBar.Append(self.FileMenu,"&File")
		self.SetMenuBar(menuBar)
		wx.EVT_MENU(self, self.idOpen, self.OnOpen)
		wx.EVT_MENU(self, self.idExit, self.OnExit)

		# Create the Options menu
		self.OptionsMenu = wx.Menu()
		self.idEnableCDDB = wx.NewId()
		self.idDeleteTocBin = wx.NewId()
		self.idDestDir = wx.NewId()
		self.idLameLoc = wx.NewId()
		self.OptionsMenu.AppendCheckItem(self.idEnableCDDB, "Enable &CDDB"," Enable CDDB")
		if self.Settings.EnableCDDB == True:
			self.OptionsMenu.Check(self.idEnableCDDB, True)
		self.OptionsMenu.AppendCheckItem(self.idDeleteTocBin,"Delete &TOC/BIN after encode",
															" Delete TOC/BIN after encode")
		if self.Settings.DeleteTocBin == True:
			self.OptionsMenu.Check(self.idDeleteTocBin, True)
		self.OptionsMenu.AppendSeparator()
		self.OptionsMenu.Append(self.idDestDir,"Set &destination directory for MP3+G files",
												" Set destination directory for MP3+G files")
		self.OptionsMenu.Append(self.idLameLoc,"Set &Lame location", " Set Lame location")
		menuBar.Append(self.OptionsMenu,"&Options")
		self.SetMenuBar(menuBar)
		wx.EVT_MENU(self, self.idEnableCDDB, self.OnEnableCDDB)
		wx.EVT_MENU(self, self.idDeleteTocBin, self.OnDeleteTocBin)
		wx.EVT_MENU(self, self.idDestDir, self.OnDestDir)
		wx.EVT_MENU(self, self.idLameLoc, self.OnLameLoc)

		# Create the Actions menu
		self.ActionsMenu = wx.Menu()
		self.idEncode = wx.NewId()
		self.idRescanCDDB = wx.NewId()
		self.ActionsMenu.Append(self.idEncode, "&Encode to MP3+G"," Encode to MP3+G")
		self.ActionsMenu.AppendSeparator()
		self.ActionsMenu.Append(self.idRescanCDDB,"R&escan CDDB"," Rescan CDDB")
		menuBar.Append(self.ActionsMenu,"&Actions")
		self.SetMenuBar(menuBar)
		wx.EVT_MENU(self, self.idEncode, self.OnEncode)
		wx.EVT_MENU(self, self.idRescanCDDB, self.OnRescanCDDB)

		# Set up event handler for worker thread done event
		EVT_DONE(self, self.OnThreadDone)
		self.ThreadDone = False
		self.worker = None


	def OnOpen(self,e):
		dlg = wx.FileDialog(self)
		if (dlg.ShowModal() == wx.ID_OK):
			fullpath = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
			self.OpenTOC (fullpath)

	def OnExit(self,e):
		self.Close(True)

	def OnEnableCDDB(self,e):
		self.Settings.EnableCDDB = self.OptionsMenu.IsChecked (self.idEnableCDDB)

	def OnDeleteTocBin(self,e):
		self.Settings.DeleteTocBin = self.OptionsMenu.IsChecked (self.idDeleteTocBin)

	def OnDestDir(self,e):
		dirDlg = wx.DirDialog(self)
		retval = dirDlg.ShowModal()
		if retval == wx.ID_OK:
			if (os.path.isdir(dirDlg.GetPath())):
				self.Settings.DestDir = dirDlg.GetPath()
			else:
				ErrorPopup ("No such directory %s" % dirDlg.GetPath())

	def OnLameLoc(self,e):
		fileDlg = wx.FileDialog(self)
		retval = fileDlg.ShowModal()
		if retval == wx.ID_OK:
			if (os.path.isfile(fileDlg.GetPath())):
				self.Settings.LameLoc = fileDlg.GetPath()
			else:
				ErrorPopup ("No such file %s" % fileDlg.GetPath())

	def OnEncode(self,e):
		ErrorPopup ("Encode")

	def OnRescanCDDB(self,e):
		self.ScanTOC(ForceCDDB = True)

	def OpenTOC (self, tocfilepath):
		self.tocDirName, self.tocFileName = os.path.split (tocfilepath)
		self.SetTitle ("%s - %s" % (TITLE_STRING, self.tocFileName))
		self.ScanTOC()

	def ScanTOC (self, ForceCDDB = False):
		fullpath = os.path.join (self.tocDirName, self.tocFileName)
		self.binfilename, self.interleaved, self.startBytes, self.trackSizeBytes = cdgdao.ParseToc (fullpath)
		# Parse the TOC file results (if it was successfully parsed)
		if not self.binfilename:
			ErrorPopup ("Error reading TOC file: No binary file mentioned, did you use read-cd mode?")
		elif (len(self.startBytes) == 0) and (len(self.trackSizeBytes) == 0):
			ErrorPopup ("Error reading TOC file: No track information found")
		else:
			self.trackStartMins = []
			self.trackStartSecs = []
			self.trackStartFrames = []
			for track in self.startBytes:
				mins, secs, frames = cdgtools.ComputeMSF (track)
				self.trackStartMins.append(mins)
				self.trackStartSecs.append(secs)
				self.trackStartFrames.append(frames)
			# Guess the leadout start based on the start offset and size of the last track
			num_tracks = len(self.trackStartMins)
			leadoutStartByte = self.startBytes[num_tracks - 1] + self.trackSizeBytes[num_tracks - 1]
			leadoutMins, leadoutSecs, leadoutFrames = cdgtools.ComputeMSF (leadoutStartByte)

			# Create generic track names in case no match found, or CDDB is disabled
			TrackNames = []
			for track in range(num_tracks):
				TrackNames.append ("track%.02d" % (track + 1))
			self.TracksPanel.StatusBar.SetStatusText ("%d tracks found" % num_tracks)

			if (self.Settings.EnableCDDB == True) or (ForceCDDB == True):
				# Do the CDDB query
				resultString, cddbDict = cdgcddb.cddbQuery (self.trackStartMins, self.trackStartSecs, 
														self.trackStartFrames, leadoutMins, leadoutSecs )
				self.TracksPanel.StatusBar.SetStatusText (resultString)

				# If a match was found, fill the track list with CDDB track names
				if cddbDict != None:
					TrackNames = []
					for i in range(num_tracks):
						# Create the track name, remove any slashes
						trackname = "%.02d - %s" % ((i + 1), cddbDict['TTITLE' + `i`])
						trackname = trackname.replace ("/", "-")
						trackname = trackname.replace ("\\", "-")
						TrackNames.append(trackname)
				# Otherwise (no CDDB match found) use generic track names

			# Fill the track list panel
			self.TracksPanel.ClearList()
			for track_num in range(num_tracks):
				self.TracksPanel.InsertItem(track_num, TrackNames[track_num])

	# Common handler for setting the progress timer and checking for cancel
	def SetProgress(self, Dlg, progress, label):

		cont = Dlg.Update(progress, label)

		# Handle both types of return value from Update() 
		if isinstance(cont, types.TupleType):
			# Later versions of wxPython return a tuple from the above.
			cont, skip = cont

		# Return True if we should keep going, otherwise cancel was clicked
		return (cont)

	def OnThreadDone(self, event):
		self.ThreadDone = True
		self.worker = None

	# Encode from main menu (encodes all tracks)
	def OnEncode (self,e):
		# Create a list of all tracks
		trackNumList = []
		for track in range (self.TracksPanel.GetItemCount()):
			trackNumList.append(track)
		self.DoEncode (trackNumList)

	# Do the actual encode
	def DoEncode (self, trackNumList):
		num_tracks = len(trackNumList)
		if num_tracks == 0:
			ErrorPopup ("No tracks to encode")
		else:
			# Set the binfile and tocfile locations (assume same dir)
			binfilepath = os.path.join (self.tocDirName, self.binfilename)
			tocfilepath = os.path.join (self.tocDirName, self.tocFileName)
			tmpfilepath = os.path.join(self.Settings.DestDir, "temp.pcm")

			# Check the binfile exists
			if (not os.path.isfile(binfilepath)):
				ErrorPopup("Bin file %s does not exist" % binfilepath)
			else:

				# Create a progress dialog.
				# The progress bar just treats each track as the same size, so
				# for 5 tracks, the update values are 20, 40, 60, 80, 100 (complete).
				progressDlg = wx.ProgressDialog ("Please wait...", "Encoding tracks",
								style=(wx.PD_CAN_ABORT | wx.PD_AUTO_HIDE | wx.PD_APP_MODAL))
				keep_going = True

				# Loop through encoding each requested track
				for track in trackNumList:

					# Update the progress bar. If cancel was pressed, quit at this point
					if num_tracks > 1:
						progress = (100 / num_tracks) * (track + 1)
					else:
						progress = 50
					keep_going = self.SetProgress (progressDlg, progress, 
									"Track %d: Ripping audio" % (track + 1))
					if keep_going == False:
						break
					else:
						# Rip the audio to a raw PCM file
						pcmdata = cdgparse.bin2pcm (binfilepath,
										self.startBytes[track],	self.trackSizeBytes[track])
						cdgparse.pcmWriteToFile (tmpfilepath, pcmdata)
						if (not os.path.isfile(tmpfilepath)):
							ErrorPopup("Cannot find raw audio rip (%s)" % tmpfilename)
							keep_going = False
							break

						# Update the progress bar. If cancel was pressed, quit at this point
						keep_going = self.SetProgress (progressDlg, progress, 
										"Track %d: MP3 encoding" % (track + 1))
						if keep_going == False:
							break
		
						# Encode with lame
						mp3name = "%s.mp3" % self.TracksPanel.GetItemText (track)
						# Quote any songnames with spaces in before calling lame
						if mp3name.find(" ") != -1:
							mp3name = "\"%s\"" % mp3name
						# Use configured lame location. If not configured, hope it's in the path
						if self.Settings.LameLoc == "":
							lameloc = "lame"
						else:
							lameloc = self.Settings.LameLoc
						# Create the lame string
						fullmp3path = os.path.join (self.Settings.DestDir, mp3name)
						lame_string = "%s -r --silent --cbr --big-endian %s %s" % (lameloc, tmpfilepath, fullmp3path)

						# Now palm off the actual execution of lame to another thread.
						# This allows the GUI to be updated because lame isn't run in
						# the GUI thread context.
						self.ThreadDone = False
						self.worker = WorkerThread (self, lame_string)
						while (self.ThreadDone == False):
							# Repaint once per second
							time.sleep(1)
							wx.Yield()

						# Update the progress bar. If cancel was pressed, quit at this point
						keep_going = self.SetProgress (progressDlg, progress, 
										"Track %d: Ripping CD+G data" % (track + 1))
						if keep_going == False:
							break
		
						# Rip the CD+G subchannel data
						cdgdata = cdgparse.bin2cdg (binfilepath,
										self.startBytes[track], self.trackSizeBytes[track])

						# Deinterleave if the data is in raw format
						if (self.interleaved):
							# Update the progress bar. If cancel was pressed, quit at this point
							keep_going = self.SetProgress (progressDlg, progress, 
											"Track %d: CD+G Deinterleaving" % (track + 1))
							if keep_going == False:
								break
							cdgdata = cdgparse.Deinterleave (cdgdata)

						# Update the progress bar. If cancel was pressed, quit at this point
						keep_going = self.SetProgress (progressDlg, progress,
										"Track %d: Writing CDG file" % (track + 1))
						if keep_going == False:
							break
	
						# Write the finished CDG data out to a file
						cdgname = "%s.cdg" % self.TracksPanel.GetItemText (track)
						fullcdgpath = os.path.join(self.Settings.DestDir, cdgname)
						cdgparse.cdgWriteToFile (fullcdgpath, cdgdata)
		
				# Finished, remove the TOC/BIN if requested (and encode wasn't cancelled)
				if (self.Settings.DeleteTocBin == True) and (keep_going == True):
					os.unlink(tocfilepath)
					os.unlink(binfilepath)

				# Delete the temporary PCM audio file
				if os.path.isfile(tmpfilepath):
					os.unlink (tmpfilepath)

				# Update the progress dialog
				self.SetProgress (progressDlg, 100, "Finished encoding all tracks")
				progressDlg = None
		

# Thread done event installer
def EVT_DONE(win, func):
	win.Connect(-1, -1, EVT_DONE_ID, func)


# Thread done handler
class ThreadDoneEvent(wx.PyEvent):
	def __init__(self, data):
		wx.PyEvent.__init__(self)
		self.SetEventType(EVT_DONE_ID)
		self.data = data


# Thread class that executes lame - so that not run in the GUI thread
class WorkerThread(Thread):
	def __init__(self, notify_window, execute_string):
		Thread.__init__(self)
		self.notify_window = notify_window
		self.execute_string = execute_string
		self.start()

	def run(self):
		# Execute lame within a secondary thread
		os.system (self.execute_string)
		# Post the event, not actually passing any data at the moment
		wx.PostEvent(self.notify_window, ThreadDoneEvent(0))


# Start the wx app
def StartGUI():
	cdgtoolsApp = wx.PySimpleApp()
	frame = cdgtoolsWindow(None, -1, TITLE_STRING)
	cdgtoolsApp.MainLoop()


# Can be started from the command line
if __name__ == "__main__":
    sys.exit(StartGUI())
