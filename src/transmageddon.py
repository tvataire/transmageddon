#! /usr/bin/env python3
# -.- coding: utf-8 -.-

# Transmageddon
# Copyright (C) 2009,2010,2011,2012 Christian Schaller <uraeus@gnome.org>
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

# DEVELOPERS NOTE: If you want to work on this code the two crucial objects are audiodata and videodata. 
# These two items are lists that contain python dictionaries. They contain almost all important 
# information about the incoming and outgoing media streams.

import sys
import os

os.environ["GST_DEBUG_DUMP_DOT_DIR"] = "/tmp"

import which
import time
from gi.repository import Notify
from gi.repository import GdkX11, Gio, Gtk, GLib, Gst, GstPbutils, GstTag
from gi.repository import GObject
GObject.threads_init()

import transcoder_engine
from urllib.parse import urlparse
import codecfinder
import about
import presets
import utils
import datetime
import langchooser

major, minor, patch, micro = Gst.version()
if (major == 1) and (patch < 0):
   print("You need version 1.0.0 or higher of Gstreamer-python for Transmageddon")
   sys.exit(1)

major, minor, patch = GObject.pygobject_version
if (major == 2) and (minor < 18):
   print("You need version 2.18.0 or higher of pygobject for Transmageddon")
   sys.exit(1)



TARGET_TYPE_URI_LIST = 80
dnd_list = [ ( 'text/uri-list', 0, TARGET_TYPE_URI_LIST ) ]

supported_containers = [
        "Ogg",		#0
        "Matroska",	#1
        "AVI",		#2
        "MPEG PS",	#3
        "MPEG TS",	#4
        "AVCHD/BD",	#5
        "FLV",		#6
        "Quicktime",	#7
        "MPEG4",	#8
        "3GPP",		#9
        "MXF",		#10
        "ASF", 		#11
        "I can not get this item to show for some reason",
        "WebM"		#12
]

supported_audio_codecs = [
       "vorbis",
       "flac",
       "mp3",
       "aac",
       "ac3",
       "speex",
       "celt",
       "amrnb",
       "wma2",
       "Opus"
]

supported_video_codecs = [
       "theora",
       "dirac",
       "h264",
       "mpeg2",
       "mpeg4",
       "h263p",
       "wmv2",
       "vp8"
]

# Maps containers to the codecs they support.  The first two elements are
# "special" in that they are the default audio/video selections for that
# container.
supported_video_container_map = {
    'Ogg':        [ 'Theora', 'Dirac', 'On2 vp8' ],
    'MXF':        [ 'H264', 'MPEG2', 'MPEG4' ],
    'Matroska':   [ 'Dirac', 'Theora', 'H264', 'On2 vp8',
                    'MPEG4', 'MPEG2', 'H263+' ],
    'AVI':        [ 'H264', 'Dirac', 'MPEG2', 'MPEG4',
                    'Windows Media Video 2', 'On2 vp8' ],
    'Quicktime':  [ 'H264', 'Dirac', 'MPEG2', 'MPEG4', 'On2 vp8' ],
    'MPEG4':      [ 'H264', 'MPEG2', 'MPEG4' ],
    'FLV':        [ 'H264'],
    '3GPP':       [ 'H264', 'MPEG2', 'MPEG4', 'H263+' ],
    'MPEG PS':    [ 'MPEG2', 'MPEG1', 'H264', 'MPEG4' ],
    'MPEG TS':    [ 'MPEG2', 'MPEG1', 'H264', 'MPEG4', 'Dirac' ],
    'AVCHD/BD':   [ 'H264' ],
    'ASF':        [ 'Windows Media Video 2' ],
    'WebM':       [ 'On2 vp8']
}

supported_audio_container_map = {
    'Ogg':   [ 'Vorbis', 'FLAC', 'Speex', 'Celt Ultra', 'Opus' ],
    'MXF':         [ 'mp3', 'AAC', 'AC3' ],
    'Matroska':    [ 'FLAC', 'AAC', 'AC3', 'Vorbis' ],
    'AVI':         [ 'mp3', 'AC3', 'Windows Media Audio 2' ],
    'Quicktime':   [ 'AAC', 'AC3', 'mp3' ],
    'MPEG4':       [ 'AAC', 'mp3' ],
    '3GPP':        [ 'AAC', 'mp3', 'AMR-NB' ],
    'MPEG PS':     [ 'mp3', 'AC3', 'AAC', 'mp2' ],
    'MPEG TS':     [ 'mp3', 'AC3', 'AAC', 'mp2' ],
    'AVCHD/BD':    [ 'AC3' ],
    'FLV':         [ 'mp3' ],
    'ASF':         [ 'Windows Media Audio 2', 'mp3'],
    'WebM':        [ 'Vorbis']

    # "No container" is 13th option here (0-12)
    # if adding more containers make sure to update code for 'No container as it is placement tied'
}

class Transmageddon(Gtk.Application):
   def __init__(self):
       Gtk.Application.__init__(self)
   
   def do_activate(self):
       self.win = TransmageddonUI(self)
       self.win.show_all()

   def do_startup (self):
       # start the application
       Gtk.Application.do_startup(self)

       # create a menu
       menu = Gio.Menu()
       # append to the menu the options
       menu.append(_("About"), "app.about")
       menu.append(_("Quit"), "app.quit")
       menu.append(_("Debug"), "app.debug")
       
       # set the menu as menu of the application
       self.set_app_menu(menu)

       # create an action for the option "new" of the menu
       debug_action = Gio.SimpleAction.new("debug", None)
       debug_action.connect("activate", self.debug_cb)
       self.add_action(debug_action)

       

       # option "about"
       about_action = Gio.SimpleAction.new("about", None)
       about_action.connect("activate", self.about_cb)
       self.add_action(about_action)

       # option "quit"
       quit_action = Gio.SimpleAction.new("quit", None)
       quit_action.connect("activate", self.quit_cb)
       self.add_action(quit_action)

   # callback function for "new"
   def debug_cb(self, action, parameter):
       dotfile = "/tmp/transmageddon-debug-graph.dot"
       pngfile = "/tmp/transmageddon-pipeline.png"
       if os.access(dotfile, os.F_OK):
           os.remove(dotfile)
       if os.access(pngfile, os.F_OK):
           os.remove(pngfile)
       Gst.debug_bin_to_dot_file (self.win._transcoder.pipeline, \
               Gst.DebugGraphDetails.ALL, 'transmageddon-debug-graph')
       # check if graphviz is installed with a simple test
       try:
           dot = which.which("dot")
           os.system(dot + " -Tpng -o " + pngfile + " " + dotfile)
           Gtk.show_uri(self.win.get_screen(), "file://"+pngfile, 0)
       except which.WhichError:
              print("The debug feature requires graphviz (dot) to be installed.")
              print("Transmageddon can not find the (dot) binary.")

   # callback function for "about"
   def about_cb(self, action, parameter):
       """
           Show the about dialog.
       """
       about.AboutDialog()

   # callback function for "quit"
   def quit_cb(self, action, parameter):
        print("You have quit.")
        self.quit()

class TransmageddonUI(Gtk.ApplicationWindow):
   def on_window_destroy(self, widget, data=None):
       Gtk.main_quit()

   def __init__(self, app):
       Gtk.Window.__init__(self, title="Transmageddon", application=app)
       """This class loads the GtkBuilder file of the UI"""
       
       # create discoverer object
       self.discovered = GstPbutils.Discoverer.new(50000000000)
       self.discovered.connect('discovered', self.succeed)
       self.discovered.start()

       self.audiorows=[] # set up the lists for holding the codec combobuttons
       self.videorows=[]
       self.audiocodecs=[]
       self.videocodecs=[]

       # set flag so we remove bogus value from menu only once
       self.bogus=0
       
       # init the notification area
       Notify.init('Transmageddon')

       # These dynamic comboboxes allow us to support files with 
       # multiple streams eventually
       def dynamic_comboboxes_audio(extra = []):
           vbox = Gtk.VBox()
           combo = Gtk.ComboBoxText.new()
           self.audiorows.append(combo)
           vbox.add(self.audiorows[0])
           return vbox

       def dynamic_comboboxes_video(streams,extra = []):
           vbox = Gtk.VBox()
           combo = Gtk.ComboBoxText.new()
           self.videorows.append(combo)
           vbox.add(self.videorows[0])
           return vbox

       self.builder = Gtk.Builder()
       self.builder.set_translation_domain("transmageddon")
       uifile = "transmageddon.ui"
       self.builder.add_from_file(uifile)

       #Define functionality of our button and main window
       self.box = self.builder.get_object("window")
       self.FileChooser = self.builder.get_object("FileChooser")
       self.videoinformation = self.builder.get_object("videoinformation")
       self.audioinformation = self.builder.get_object("audioinformation")
       self.videocodec = self.builder.get_object("videocodec")
       self.audiocodec = self.builder.get_object("audiocodec")
       self.audiobox = dynamic_comboboxes_audio(GObject.TYPE_PYOBJECT)
       self.videobox = dynamic_comboboxes_video(GObject.TYPE_PYOBJECT)
       self.CodecBox = self.builder.get_object("CodecBox")
       self.presetchoice = self.builder.get_object("presetchoice")
       self.containerchoice = self.builder.get_object("containerchoice")
       self.rotationchoice = self.builder.get_object("rotationchoice")
       self.transcodebutton = self.builder.get_object("transcodebutton")
       self.ProgressBar = self.builder.get_object("ProgressBar")
       self.cancelbutton = self.builder.get_object("cancelbutton")
       self.StatusBar = self.builder.get_object("StatusBar")
       self.CodecBox.attach(self.audiobox, 0, 1, 1, 2, yoptions = Gtk.AttachOptions.FILL)
       self.CodecBox.attach(self.videobox, 2, 3, 1, 2, yoptions = Gtk.AttachOptions.FILL)
       self.CodecBox.show_all()
       self.containerchoice.connect("changed", self.on_containerchoice_changed)
       self.presetchoice.connect("changed", self.on_presetchoice_changed)
       self.audiorows[0].connect("changed", self.on_audiocodec_changed)
       self.audiorows[0].set_name("audiorow0")
       self.videorows[0].connect("changed", self.on_videocodec_changed)
       self.rotationchoice.connect("changed", self.on_rotationchoice_changed)


       self.window=self.builder.get_object("window")
       self.builder.connect_signals(self) # Initialize User Interface
       self.add(self.box)

       
       def get_file_path_from_dnd_dropped_uri(self, uri):
           # get the path to file
           path = ""
           if uri.startswith('file:\\\\\\'): # windows
               path = uri[8:] # 8 is len('file:///')
           elif uri.startswith('file://'): # nautilus, rox
               path = uri[7:] # 7 is len('file://')
           elif uri.startswith('file:'): # xffm
               path = uri[5:] # 5 is len('file:')
           return path


       # This could should be fixed and re-enabled to allow drag and drop

       def on_drag_data_received(widget, context, x, y, selection, target_type, \
               timestamp):
           if target_type == TARGET_TYPE_URI_LIST:
               uri = selection.data.strip('\r\n\x00')
               self.builder.get_object ("FileChooser").set_uri(uri)

       self.start_time = False
       
       # Set the Videos XDG UserDir as the default directory for the filechooser
       # also make sure directory exists
       #if 'get_user_special_dir' in GLib.__dict__:
       self.videodirectory = \
                   GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS)
       self.audiodirectory = \
                   GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_MUSIC)
       if self.videodirectory is None:
           self.videodirectory = os.getenv('HOME')
           self.audiodirectory = os.getenv('HOME')
       CheckDir = os.path.isdir(self.videodirectory)
       if CheckDir == (False):
           os.mkdir(self.videodirectory)
       CheckDir = os.path.isdir(self.audiodirectory)
       if CheckDir == (False):
           os.mkdir(self.audiodirectory)
       self.FileChooser.set_current_folder(self.videodirectory)

       # Setting AppIcon
       FileExist = os.path.isfile("../../share/pixmaps/transmageddon.svg")
       if FileExist:
           self.set_icon_from_file( \
                   "../../share/pixmaps/transmageddon.svg")
       else:
           try:
               self.set_icon_from_file("transmageddon.svg")
           except:
               print("failed to find appicon")

       # default all but top box to insensitive by default
       # self.containerchoice.set_sensitive(False)
       self.CodecBox.set_sensitive(False)
       self.transcodebutton.set_sensitive(False)
       self.cancelbutton.set_sensitive(False)
       self.presetchoice.set_sensitive(False)
       self.containerchoice.set_sensitive(False)
       self.rotationchoice.set_sensitive(False)
       
       # set default values for various variables
       self.ProgressBar.set_text(_("Transcoding Progress"))
       self.containertoggle=False # used to not check for encoders with pbutils
       self.discover_done=False # lets us know that discover is finished
       self.missingtoggle=False
       self.havevideo=False # tracks if input file got video
       self.haveaudio=False
       self.nocontaineroptiontoggle=False

       # create variables to store passthrough options slot in the menu
       self.audiopassmenuno=1
       self.videopassmenuno=1
       self.videonovideomenuno=-2
       # create toggle so I can split codepath depending on if I using a preset
       # or not
       self.usingpreset=False
       self.presetaudiocodec=Gst.Caps.new_empty()
       self.presetvideocodec=Gst.Caps.new_empty()
       self.nocontainernumber = int(13) # this needs to be set to the number of the no container option in the menu (from 0)
       self.p_duration = Gst.CLOCK_TIME_NONE
       self.p_time = Gst.Format.TIME
       self.audiostreamids=[] # (list of stream ids)
       self.videostreamids=[]
       self.audiostreamcounter=int(-1)
       self.videostreamcounter=int(-1)

       # these 2 variables is for handling the text generated from discoverer
       self.markupaudioinfo=[]
       self.markupvideoinfo=[]

       # this value will store the short name for the container formats that we use in the UI
       self.containershort="Ogg"
       
       # These two list objects will hold all crucial media data in the form of python dictionaries.
       self.audiodata =[]
       self.videodata =[]
       # all other data will go into streamdata
       self.streamdata = {'filechoice' : False, 'filename' : False, 'outputdirectory' : False, 'container' : False, 'devicename' : "nopreset", 'multipass': 0, 'passcounter': 0, 'outputfilename' : False, 'timestamp': False}

       # Populate the Container format combobox
       # print("do we try to populate container choice")
       for i in supported_containers:
           self.containerchoice.append_text(i)
       # add i18n "No container"option
       self.containerchoice.append_text(_("No container (Audio-only)"))

       # Populate the rotatation box
       # print("populating rotationbox")
       self.rotationlist = [_("No rotation (default)"),\
                            _("Clockwise 90 degrees"), \
                            _("Rotate 180 degrees"),
                            _("Counterclockwise 90 degrees"), \
                            _("Horizontal flip"),
                            _("Vertical flip"), \
                            _("Upper left diagonal flip"),
                            _("Upper right diagnonal flip") ]

       for y in self.rotationlist: 
           self.rotationchoice.append_text(y)

       self.rotationchoice.set_active(0)
       if self.videodata:
           self.videodata[0]['rotationvalue'] = int(0)
      
       # Populate Device Presets combobox
       # print("starting preset population")
       devicelist = []
       shortname = []
       preset_list = sorted(list(presets.get().items()),
                            key = (lambda x: x[1].make + x[1].model))
       for x, (name, device) in enumerate(preset_list):
           self.presetchoice.append_text(str(device))
           devicelist.append(str(device))
           shortname.append(str(name))

       for (name, device) in (list(presets.get().items())):
           shortname.append(str(name))
       # self.presetchoices = dict(zip(devicelist, shortname))
       self.presetchoices = shortname
       self.presetchoice.prepend_text(_("No Presets"))

       self.waiting_for_signal="False"


   # define the media structures here as the canonical location. This structure should include 
   # everything needed for the pipelines. 
   # * Use strings to describe the type of data to be stored.
   # * The two caps values should be GStreamer caps objects, not caps in string format. 
   # * When a row is added, any data you are missing at that point should be replaced by '
   #   False' 
   # * The difference between passthrough and do passthrough is that the first one 
   #   states if passthrough mode is possible, the second states if the user actually 
   #   wants the stream to be passed through or not.
   # * Any value which doesn't belong into audiodata or videodata, should go into streamdata

   def add_audiodata_row(self, audiochannels, samplerate, inputaudiocaps, outputaudiocaps, streamid, canpassthrough, dopassthrough, language):
       audiodata = {'audiochannels' : audiochannels, 'samplerate' : samplerate, 'inputaudiocaps' : inputaudiocaps, 'outputaudiocaps' : outputaudiocaps , 'streamid' : streamid, 'canpassthrough' : canpassthrough, 'dopassthrough' : dopassthrough, 'language' : language }
       return audiodata

   def add_videodata_row(self, videowidth, videoheight, inputvideocaps, outputvideocaps, videonum, videodenom, streamid, canpassthrough, dopassthrough, interlaced, rotationvalue):
        videodata = { 'videowidth' : videowidth, 'videoheight' : videoheight, 'inputvideocaps' : inputvideocaps, 'outputvideocaps' : outputvideocaps, 'videonum' : videonum, 'videodenom' :  videodenom, 'streamid' : streamid, 'canpassthrough' : canpassthrough, 'dopassthrough' : dopassthrough, 'interlaced' : interlaced, 'rotationvalue' : rotationvalue }
        return videodata

   # Get all preset values
   def reverse_lookup(self,v):
       for k in codecfinder.codecmap:
           if codecfinder.codecmap[k] == v:
               return k

   def provide_presets(self,devicename):
       devices = presets.get()
       device = devices[devicename]
       preset = device.presets["Normal"]
       self.usingpreset=True
       self.containerchoice.set_active(-1) # resetting to -1 to ensure population of menu triggers
       self.presetaudiocodec=Gst.caps_from_string(preset.acodec.name)
       self.audiodata[0]['outputaudiocaps']=Gst.caps_from_string(preset.acodec.name)
       self.presetvideocodec=Gst.caps_from_string(preset.vcodec.name)
       self.videodata[0]['outputvideocaps']=Gst.caps_from_string(preset.vcodec.name)
       if preset.container == "application/ogg":
           self.containerchoice.set_active(0)
       elif preset.container == "video/x-matroska":
           self.containerchoice.set_active(1)
       elif preset.container == "video/x-msvideo":
           self.containerchoice.set_active(2)
       elif preset.container == "video/mpeg,mpegversion=2,systemstream=true":
           self.containerchoice.set_active(3)
       elif preset.container == "video/mpegts,systemstream=true,packetsize=188":
           self.containerchoice.set_active(4)
       elif preset.container == "video/mpegts,systemstream=true,packetsize=192":
           self.containerchoice.set_active(5)
       elif preset.container == "video/x-flv":
           self.containerchoice.set_active(6)
       elif preset.container == "video/quicktime,variant=apple":
           self.containerchoice.set_active(7)
       elif preset.container == "video/quicktime,variant=iso":
           self.containerchoice.set_active(8)
       elif preset.container == "video/quicktime,variant=3gpp":
           self.containerchoice.set_active(9)
       elif preset.container == "application/mxf":
           self.containerchoice.set_active(10)
       elif preset.container == "video/x-ms-asf":
           self.containerchoice.set_active(11)
       elif preset.container == "video/webm":
           self.containerchoice.set_active(12)
       else:
            print("failed to set container format from preset data")


       # Check for number of passes
       passes = preset.vcodec.passes
       if passes == "0":
           self.streamdata['multipass'] = 0
       else:
           self.streamdata['multipass'] = int(passes)
           self.streamdata['passcounter'] = int(0)

   # Create query on uridecoder to get values to populate progressbar 
   # Notes:
   # Query interface only available on uridecoder, not decodebin2)
   # FORMAT_TIME only value implemented by all plugins used
   # a lot of original code from Gst-python synchronizer.py example
   def Increment_Progressbar(self):
       # print("incrementing progressbar")
       if self.start_time == False:  
           self.start_time = time.time()
       try:
           success, position = \
                   self._transcoder.uridecoder.query_position(Gst.Format.TIME)
       except:
           position = Gst.CLOCK_TIME_NONE

       try:
           success, duration = \
                   self._transcoder.uridecoder.query_duration(Gst.Format.TIME)
       except:
           duration = Gst.CLOCK_TIME_NONE
       if position != Gst.CLOCK_TIME_NONE:
           if duration != 0:
               value = float(position) / duration
               if float(value) < (1.0) and float(value) >= 0:
                   self.ProgressBar.set_fraction(value)
                   percent = (value*100)
                   timespent = time.time() - self.start_time
                   percent_remain = (100-percent)
                   if percent != 0:
                       rem = (timespent / percent) * percent_remain
                   else: 
                       rem = 0.1
                   min = rem / 60
                   sec = rem % 60
                   time_rem = _("%(min)d:%(sec)02d") % {
                       "min": min,
                       "sec": sec,
                       }
                   if percent_remain > 0.5:
                       if self.streamdata['passcounter'] == int(0):
                           txt = "Estimated time remaining: %(time)s"
                           self.ProgressBar.set_text(_(txt) % \
                                {'time': str(time_rem)})
                       else:
                           txt = "Pass %(count)d time remaining: %(time)s"
                           self.ProgressBar.set_text(_(txt) % { \
                               'count': self.streamdata['passcounter'], \
                               'time': str(time_rem), })
                   return True
               else:
                   self.ProgressBar.set_fraction(0.0)
                   return False
           else:
               return False

   # Call GObject.timeout_add with a value of 500millisecond to regularly poll
   # for position so we can
   # use it for the progressbar
   def ProgressBarUpdate(self, source):
       GObject.timeout_add(500, self.Increment_Progressbar)

   def _on_eos(self, source):
       context_id = self.StatusBar.get_context_id("EOS")
       if self.streamdata['passcounter'] == int(0):
           self.StatusBar.push(context_id, (_("File saved to %(dir)s") % \
                   {'dir': self.streamdata['outputdirectory']}))
           uri = "file://" + os.path.abspath(os.path.curdir) + "/transmageddon.svg"
           notification = Notify.Notification.new("Transmageddon", (_("%(file)s saved to %(dir)s") % {'dir': self.streamdata['outputdirectory'], 'file': self.streamdata['outputfilename']}), uri)
           notification.show()
           self.FileChooser.set_sensitive(True)
           self.containerchoice.set_sensitive(True)
           self.CodecBox.set_sensitive(True)
           self.presetchoice.set_sensitive(True)
           self.cancelbutton.set_sensitive(False)
           self.transcodebutton.set_sensitive(True)
           self.rotationchoice.set_sensitive(True)
           self.start_time = False
           self.ProgressBar.set_text(_("Done Transcoding"))
           self.ProgressBar.set_fraction(1.0)
           self.start_time = False
           self.streamdata['multipass'] = 0
           self.streamdata['passcounter'] = 0
           x=0
           while x <= self.audiostreamcounter:
               self.audiodata[x]['dopassthrough']=False
               self.audiodata[x]['canpassthrough']=False
               x=x+1
           self.videodata[0]['dopassthrough']=False
           self.videodata[0]['canpassthrough']=False
           self.houseclean=False # due to not knowing which APIs to use I need
                                 # this toggle to avoid errors when cleaning
                                 # the codec comboboxes
       else:
           self.start_time = False
           if self.streamdata['passcounter'] == (self.streamdata['multipass']-1):
               self.StatusBar.push(context_id, (_("Writing %(filename)s") % {'filename': self.streamdata['outputfilename']}))
               self.streamdata['passcounter'] = int(0)
               self._start_transcoding()
           else:
               self.StatusBar.push(context_id, (_("Pass %(count)d Complete. ") % \
                   {'count': self.streamdata['passcounter']}))
               self.streamdtata['passcounter'] = self.streamdata['passcounter']+1
               self._start_transcoding()

 
   def succeed(self, discoverer, info, error):

       result=GstPbutils.DiscovererInfo.get_result(info)
       if result != GstPbutils.DiscovererResult.ERROR:
           streaminfo=info.get_stream_info()
           if streaminfo != None:
               self.streamdata['container'] = streaminfo.get_caps()
           else:
               print("FIXME")
               #self.check_for_elements()
           seekbool = info.get_seekable()
           clipduration=info.get_duration()
           for i in info.get_stream_list():
               if isinstance(i, GstPbutils.DiscovererAudioInfo):
                   streamid=i.get_stream_id()
                   if streamid not in self.audiostreamids:
                       self.audiostreamcounter=self.audiostreamcounter+1
                       self.audiostreamids.append(streamid)
                       self.haveaudio=True
                       self.audiodata.append(self.add_audiodata_row(i.get_channels(), i.get_sample_rate(), i.get_caps(), False, streamid, False, False, i.get_language()))
                       if self.audiodata[self.audiostreamcounter]['language']== None:
                           # load language setting ui
                           output=langchooser.languagechooser(self)
                           output.languagewindow.run()
                           self.audiodata[self.audiostreamcounter]['language'] = output.langcode

                           # self.audiodata[self.audiostreamcounter]['language']=_("Unknown language")
                       if self.audiostreamcounter > 0:
                           combo = Gtk.ComboBoxText.new()
                           self.audiorows.append(combo)
                           self.audiobox.add(self.audiorows[self.audiostreamcounter])
                           self.audiorows[self.audiostreamcounter].connect("changed", self.on_audiocodec_changed)
                           self.audiorows[self.audiostreamcounter].set_name("audiorow"+str(self.audiostreamcounter))
                           self.audiorows[self.audiostreamcounter].show()

                       self.containerchoice.set_active(-1) # set this here to ensure it happens even with quick audio-only
                       self.containerchoice.set_active(0)

               if isinstance(i, GstPbutils.DiscovererVideoInfo):
                   streamid=i.get_stream_id()
                   if streamid not in self.videostreamids:
                       videotags=i.get_tags()
                       self.havevideo=True
                       self.videostreamids.append(streamid)
                       # put all video data into a dictionary. The two False values are ouputvideocaps and 
                       # the two passthrough booleans which will be set later.
                       self.videodata.append(self.add_videodata_row(i.get_width(),i.get_height(), i.get_caps(), False, i.get_framerate_num(), i.get_framerate_denom(), streamid, False, False, i.is_interlaced(), False))
                       self.populate_menu_choices() # run this to ensure video menu gets filled
                       self.presetchoice.set_sensitive(True)
                       self.videorows[0].set_sensitive(True)
                       self.rotationchoice.set_sensitive(True)
               self.discover_done=True
               self.transcodebutton.set_sensitive(True)

               if self.waiting_for_signal == True:
                   if self.containertoggle == True:
                       if self.streamdata['container'] != False:
                           self.check_for_passthrough(self.streamdata['container'])
                   else:
                       # self.check_for_elements()
                       if self.missingtoggle==False:
                           self._start_transcoding()
               if self.streamdata['container'] != False:
                   self.check_for_passthrough(self.streamdata['container'])
       
           # set UI markup, will wary in size depending on number of streams         

           if self.haveaudio:
               self.markupaudioinfo=[]
               if self.audiostreamcounter==0:
                   self.markupaudioinfo.append(''.join(('<small>','Audio channels: ', str(self.audiodata[self.audiostreamcounter]['audiochannels']), '</small>',"\n", '<small>','Audio codec: ',str(GstPbutils.pb_utils_get_codec_description(self.audiodata[self.audiostreamcounter]['inputaudiocaps'])), "\n", 'Language: ', self.audiodata[self.audiostreamcounter]['language'],'</small>')))
                   self.audioinformation.set_markup("".join(self.markupaudioinfo))
               else:
                   if self.audiostreamcounter==1:
                       x=0
                       while x <= self.audiostreamcounter:
                           self.markupaudioinfo.append(''.join(('<small>','<b>','Audiostream no: ',str(x+1),'</b>','</small>',"\n",'<small>','Audio channels: ', str(self.audiodata[x]['audiochannels']), '</small>',"\n", '<small>','Audio codec: ',str(GstPbutils.pb_utils_get_codec_description(self.audiodata[x]['inputaudiocaps'])), "\n", 'Language: ', self.audiodata[x]['language'],'</small>',"\n")))
                           self.audioinformation.set_markup("".join(self.markupaudioinfo))
                           x=x+1

           else: # if there is no audio streams
               self.audioinformation.set_markup(''.join(('<small>', _("No Audio"), '</small>',"\n", '<small>', "",'</small>')))
               if not self.audiodata: # creates empty data set
                   self.audiodata.append(self.add_audiodata_row(None, None, None, False, None, False, False, None))

           if self.havevideo==True:
               self.videoinformation.set_markup(''.join(('<small>', 'Video width&#47;height: ', str(self.videodata[0]['videowidth']), "x", str(self.videodata[0]['videoheight']), '</small>',"\n", '<small>', 'Video codec: ',  str(GstPbutils.pb_utils_get_codec_description   (self.videodata[0]['inputvideocaps'])), '</small>' )))
           else: # in case of media being audio-only
               if not self.videodata: # need to create this for non-video files too
                   self.videodata.append(self.add_videodata_row(None, None, None, False, None, None, None, False, False, None)) 
               self.videoinformation.set_markup(''.join(('<small>', _("No Video"), '</small>', "\n", '<small>', "", '</small>')))
               self.presetchoice.set_sensitive(False)
               self.videorows[0].set_sensitive(False)
               self.rotationchoice.set_sensitive(False)
       else:
          print("hoped for a great discovery; got an error")
          print(result)
          print(error)

   def discover(self, path):
       self.discovered.discover_uri_async("file://"+path)

   def mediacheck(self, FileChosen):
       uri = urlparse (FileChosen)
       path = uri.path
       self.discover(path)
   
   def check_for_passthrough(self, containerchoice):
       videointersect = Gst.Caps.new_empty()
       audiointersect = []
       for x in self.audiostreamids:
           audiointersect.append(Gst.Caps.new_empty())
       if containerchoice != False:
           # container = codecfinder.containermap[containerchoice]
           containerelement = codecfinder.get_muxer_element(containerchoice)
           if containerelement == False:
               self.containertoggle = True
           else:
               factory = Gst.Registry.get().lookup_feature(containerelement)
               for x in factory.get_static_pad_templates():
                   if (x.direction == Gst.PadDirection.SINK):
                       sourcecaps = x.get_caps()
                       if self.havevideo == True:
                           if videointersect.is_empty():
                               videointersect = sourcecaps.intersect(self.videodata[0]['inputvideocaps'])
                           if videointersect.is_empty():
                               self.videodata[0]['canpassthrough']=False
                           else:
                               self.videodata[0]['canpassthrough']=True

                       if self.haveaudio == True:
                           y=0
                           count=len(self.audiostreamids)
                           while y < count:
                               if audiointersect[y].is_empty():
                                   audiointersect[y] = sourcecaps.intersect(self.audiodata[y]['inputaudiocaps'])
                               if audiointersect[y].is_empty():
                                   self.audiodata[y]['canpassthrough']=False
                               else:
                                   self.audiodata[y]['canpassthrough']=True
                               y=y+1
              

   # define the behaviour of the other buttons
   def on_FileChooser_file_set(self, widget):
       self.filename = self.builder.get_object ("FileChooser").get_filename()
       # These two list objects will hold all crucial media data in the form of python dictionaries.
       self.audiodata =[]
       self.videodata =[]
       self.audiostreamids=[] # (list of stream ids)
       self.videostreamids=[]
       self.audiostreamcounter=-1
       if self.filename is not None: 
           self.haveaudio=False #make sure to reset these for each file
           self.havevideo=False #
           self.mediacheck(self.filename)
           self.ProgressBar.set_fraction(0.0)
           self.ProgressBar.set_text(_("Transcoding Progress"))
           if (self.havevideo==False and self.nocontaineroptiontoggle==False):
               self.nocontaineroptiontoggle=True
           else:
               self.presetchoice.set_sensitive(True)
               self.presetchoice.set_active(0)

               # removing bogus text from supported_containers
               if self.bogus==0:
                   self.containerchoice.remove(12)
                   self.bogus=1
               self.nocontaineroptiontoggle=False
           self.containerchoice.set_sensitive(True)

   def _start_transcoding(self): 
       self.streamdata['filechoice'] = self.builder.get_object ("FileChooser").get_uri()
       # self.filename = self.builder.get_object ("FileChooser").get_filename()
       if (self.havevideo and (self.videodata[0]['outputvideocaps'] != "novid")):
           self.streamdata['outputdirectory']=self.videodirectory
       else:
           self.streamdata['outputdirectory']=self.audiodirectory

       self._transcoder = transcoder_engine.Transcoder(self.streamdata,
                        self.audiodata, self.videodata)
        

       self._transcoder.connect("ready-for-querying", self.ProgressBarUpdate)
       self._transcoder.connect("got-eos", self._on_eos)
       self._transcoder.connect("missing-plugin", self.install_plugin)
       return True

   def install_plugin(self, signal):
       plugin=GstPbutils.missing_plugin_message_get_installer_detail(self._transcoder.missingplugin)
       missing = []
       missing.append(plugin)
       self.context = GstPbutils.InstallPluginsContext ()
       self.context.set_xid(self.get_window().get_xid())
       GstPbutils.install_plugins_async (missing, self.context, \
                       self.donemessage, "NULL")
       self.on_cancelbutton_clicked("click")

   def donemessage(self, donemessage, null):
       if donemessage == GstPbutils.InstallPluginsReturn.SUCCESS:
           if Gst.update_registry():
               print("Plugin registry updated, trying again")
           else:
               print("Gstreamer registry update failed")
           if self.containertoggle == False:
               # FIXME - might want some test here to check plugins needed are
               # actually installed
               # but it is a rather narrow corner case when it fails
               self._start_transcoding()
       elif donemessage == GstPbutils.InstallPluginsReturn.PARTIAL_SUCCESS:
           print("Plugin install not fully succesfull")
       elif donemessage == GstPbutils.InstallPluginsReturn.INVALID:
           context_id = self.StatusBar.get_context_id("EOS")
           self.StatusBar.push(context_id, \
                   _("Got an invalid response from codec installer, can not install missing codec."))
       elif donemessage == GstPbutils.InstallPluginsReturn.HELPER_MISSING:
           context_id = self.StatusBar.get_context_id("EOS")
           self.StatusBar.push(context_id, \
                   _("No Codec installer helper application available."))
       elif donemessage == GstPbutils.InstallPluginsReturn.NOT_FOUND:
           context_id = self.StatusBar.get_context_id("EOS")
           self.StatusBar.push(context_id, \
                   _("Plugins not found, choose different codecs."))
           self.FileChooser.set_sensitive(True)
           self.containerchoice.set_sensitive(True)
           self.CodecBox.set_sensitive(True)
           self.cancelbutton.set_sensitive(False)
           self.transcodebutton.set_sensitive(True)
       elif donemessage == GstPbutils.InstallPluginsReturn.USER_ABORT:
           self._cancel_encoding = \
               transcoder_engine.Transcoder.Pipeline(self._transcoder,"null")
           context_id = self.StatusBar.get_context_id("EOS")
           self.StatusBar.push(context_id, _("Codec installation aborted."))
           self.FileChooser.set_sensitive(True)
           self.containerchoice.set_sensitive(True)
           self.CodecBox.set_sensitive(True)
           self.cancelbutton.set_sensitive(False)
           self.transcodebutton.set_sensitive(True)
       else:
           context_id = self.StatusBar.get_context_id("EOS")
           self.StatusBar.push(context_id, _("Missing plugin installation failed."))


   def check_for_elements(self, streamno):
       # print("checking for elements")
       # this function checks for missing plugins using pbutils
       if self.streamdata['container']==False:
           containerstatus=True
           videostatus=True
       else:
           containerchoice = self.builder.get_object ("containerchoice").get_active_text ()
           if containerchoice != None:
               containerstatus = codecfinder.get_muxer_element(codecfinder.containermap[containerchoice])
               if self.havevideo:
                   if self.videodata[0]['dopassthrough'] != True:
                       if self.VideoCodec == "novid":
                           videostatus=True
                       else:
                           videostatus = codecfinder.get_video_encoder_element(self.VideoCodec)
                   else:
                       videostatus=True
       if self.haveaudio:
           if self.audiodata[FIXME]['dopassthrough'] != True:
               audiostatus = codecfinder.get_audio_encoder_element(self.audiodata[streamno]['outputaudiocaps'])
           else:
               audiostatus=True
       else:
           audiostatus=True
       if self.havevideo == False: # this flags help check if input is audio-only file
           videostatus=True
       if not containerstatus or not videostatus or not audiostatus:
           self.missingtoggle=True
           fail_info = []
           if self.containertoggle==True:
               audiostatus=True
               videostatus=True
           if containerstatus == False:
               fail_info.append(Gst.caps_from_string(codecfinder.containermap[containerchoice]))
           if audiostatus == False:
               fail_info.append(self.audiodata[0]['outputaudiocodec'])
           if videostatus == False:
               fail_info.append(self.videodata[0]['outputvideocodec'])
           missing = []
           for x in fail_info:
               missing.append(GstPbutils.missing_encoder_installer_detail_new(x))
           context = GstPbutils.InstallPluginsContext ()
           context.set_xid(self.get_window().get_xid())
           GstPbutils.install_plugins_async (missing, context, \
                       self.donemessage, "NULL")

   # The transcodebutton is the one that calls the Transcoder class and thus
   # starts the transcoding
   def on_transcodebutton_clicked(self, widget):
       self.containertoggle = False
       self.FileChooser.set_sensitive(False)
       self.containerchoice.set_sensitive(False)
       self.presetchoice.set_sensitive(False)
       self.CodecBox.set_sensitive(False)
       self.transcodebutton.set_sensitive(False)
       self.rotationchoice.set_sensitive(False)
       self.cancelbutton.set_sensitive(True)
       self.ProgressBar.set_fraction(0.0)
       # create a variable with a timestamp code
       timeget = datetime.datetime.now()
       self.streamdata['timestamp'] = str(timeget.strftime("-%H%M%S-%d%m%Y"))
       # Remove suffix from inbound filename so we can reuse it together with suffix to create outbound filename
       self.nosuffix = os.path.splitext(os.path.basename(self.filename))[0]
       # pick output suffix
       container = self.builder.get_object("containerchoice").get_active_text()
       if self.streamdata['container']==False: # deal with container less formats
           self.ContainerFormatSuffix = codecfinder.nocontainersuffixmap[Gst.Caps.to_string(self.audiodata['outputaudiocaps'])]
       else:
           if self.havevideo == False:
               self.ContainerFormatSuffix = codecfinder.audiosuffixmap[container]
           else:
               self.ContainerFormatSuffix = codecfinder.csuffixmap[container]
       self.streamdata['outputfilename'] = str(self.nosuffix+self.streamdata['timestamp']+self.ContainerFormatSuffix)
       context_id = self.StatusBar.get_context_id("EOS")
       self.StatusBar.push(context_id, (_("Writing %(filename)s") % {'filename': self.streamdata['outputfilename']}))
       if self.streamdata['multipass'] != 0:
           self.passcounter=int(1)
           self.StatusBar.push(context_id, (_("Pass %(count)d Progress") % {'count': self.passcounter}))
       if self.haveaudio:
           if "samplerate" in self.audiodata[0]:
               # self.check_for_elements()
               if self.missingtoggle==False:
                   self._start_transcoding()
           else:
               self.waiting_for_signal="True"
       elif self.havevideo:
           if "videoheight" in self.videodata[0]:
               # self.check_for_elements()
               if self.missingtoggle==False:
                   self._start_transcoding()
           else:
               self.waiting_for_signal="True"

   def on_cancelbutton_clicked(self, widget):
       self.FileChooser.set_sensitive(True)
       self.containerchoice.set_sensitive(True)
       self.CodecBox.set_sensitive(True)
       self.presetchoice.set_sensitive(True)
       self.rotationchoice.set_sensitive(True)
       self.presetchoice.set_active(0)
       self.cancelbutton.set_sensitive(False)
       self.transcodebutton.set_sensitive(True)
       self._cancel_encoding = \
               transcoder_engine.Transcoder.Pipeline(self._transcoder,"null")
       self.ProgressBar.set_fraction(0.0)
       self.ProgressBar.set_text(_("Transcoding Progress"))
       context_id = self.StatusBar.get_context_id("EOS")
       self.StatusBar.pop(context_id)

   def populate_menu_choices(self):
       # self.audiocodecs - contains list of whats in self.audiorows
       # self.videocodecs - contains listof whats in self.videorows
       # audio_codecs, video_codecs - temporary lists

       # clean up stuff from previous run
       self.houseclean=True # set this to avoid triggering events when cleaning out menus
       x=0
       while x <= self.audiostreamcounter:
           if self.audiocodecs:
               for c in self.audiocodecs[x]: # 
                   self.audiorows[x].remove(0)
               if x==self.audiostreamcounter:
                   self.audiocodecs=[]
           if self.havevideo==True:
               if self.streamdata['container'] != False:
                   for c in self.videocodecs:
                       self.videorows[x].remove(0)
                   self.videocodecs=[]
           x=x+1
       self.houseclean=False

           # end of housecleaning

       # start filling audio
       if self.haveaudio==True:
           x=0
           while x <= self.audiostreamcounter:
               self.audiocodecs.append([])
               if self.usingpreset==True: # First fill menu based on presetvalue
                   testforempty = self.presetaudiocodec.to_string()
                   if testforempty != "EMPTY": 
                       self.audiorows[x].append_text(str(GstPbutils.pb_utils_get_codec_description(self.presetaudiocodec)))
                       self.audiorows[x].set_active(0)
                       self.audiocodecs[x].append(self.presetaudiocodec)
               elif self.streamdata['container']==False: # special setup for container less case, looks ugly, but good enough for now
                       self.audiorows[x].append_text(str(GstPbutils.pb_utils_get_codec_description(Gst.caps_from_string("audio/mpeg, mpegversion=(int)1, layer=(int)3"))))
                       self.audiorows[x].append_text(str(GstPbutils.pb_utils_get_codec_description(Gst.caps_from_string("audio/mpeg, mpegversion=4, stream-format=adts"))))
                       self.audiorows[x].append_text(str(GstPbutils.pb_utils_get_codec_description(Gst.caps_from_string("audio/x-flac"))))
                       self.audiocodecs[x].append(Gst.caps_from_string("audio/mpeg, mpegversion=(int)1, layer=(int)3"))
                       self.audiocodecs[x].append(Gst.caps_from_string("audio/mpeg, mpegversion=4, stream-format=adts"))
                       self.audiocodecs[x].append(Gst.caps_from_string("audio/x-flac"))
                       self.audiorows[x].set_active(0)
                       self.audiorows[x].set_sensitive(True)
               else:
                       audiolist = []
                       audio_codecs = supported_audio_container_map[self.containershort]
                       for c in audio_codecs:
                           self.audiocodecs[x].append(Gst.caps_from_string(codecfinder.codecmap[c]))
                       for c in self.audiocodecs[x]: # Use codec descriptions from GStreamer
                           self.audiorows[x].append_text(GstPbutils.pb_utils_get_codec_description(c))

               if self.audiodata[x]['canpassthrough']==True:
                       self.audiorows[x].append_text(_("Audio passthrough"))
                       self.audiocodecs[x].append("pass")
                       self.audiopassmenuno=(len(self.audiocodecs[x]))-1 #FIXME

               self.audiorows[x].set_sensitive(True)
               self.audiorows[x].set_active(0)
               x=x+1
       else:
           self.audiorows[x].set_sensitive(False)

       # fill in with video
       if self.havevideo==True:
           if self.streamdata['container'] != False:
               if self.usingpreset==True:
                   testforempty = self.presetvideocodec.to_string()
                   if testforempty != "EMPTY":
                       self.videorows[0].append_text(str(GstPbutils.pb_utils_get_codec_description(self.presetvideocodec)))
                       self.videorows[0].set_active(0)
                       self.videocodecs.append(self.presetvideocodec)
               else:
                   video_codecs=[]
                   video_codecs = supported_video_container_map[self.containershort]
                   self.rotationchoice.set_sensitive(True)
                   for c in video_codecs:
                       self.videocodecs.append(Gst.caps_from_string(codecfinder.codecmap[c]))
                   for c in self.videocodecs: # Use descriptions from GStreamer
                       self.videorows[0].append_text(GstPbutils.pb_utils_get_codec_description(c))
                   self.videorows[0].set_sensitive(True)
                   self.videorows[0].set_active(0)

                   #add a 'No Video option'
                   self.videorows[0].append_text(_("No Video"))
                   self.videocodecs.append("novid")
                   self.videonovideomenuno=(len(self.videocodecs))-1
                      
                   # add the Passthrough option 
                   if self.videodata[0]['canpassthrough']==True:
                       self.videorows[0].append_text(_("Video passthrough"))
                       self.videocodecs.append("pass")
                       self.videopassmenuno=(len(self.videocodecs))-1

   def on_containerchoice_changed(self, widget):
       self.CodecBox.set_sensitive(True)
       self.ProgressBar.set_fraction(0.0)
       self.ProgressBar.set_text(_("Transcoding Progress"))
       if self.builder.get_object("containerchoice").get_active() == self.nocontainernumber:
               self.streamdata['container'] = False
               self.videorows[0].set_active(self.videonovideomenuno)
               self.videorows[0].set_sensitive(False)
       else:
           if self.builder.get_object("containerchoice").get_active()!= -1:
               self.containershort=self.builder.get_object ("containerchoice").get_active_text()
               self.streamdata['container'] = Gst.caps_from_string(codecfinder.containermap[self.containershort])
               # self.check_for_elements()
       if self.discover_done == True:
           self.check_for_passthrough(self.streamdata['container'])
           self.populate_menu_choices()
           self.transcodebutton.set_sensitive(True)


   def on_presetchoice_changed(self, widget):
       presetchoice = self.builder.get_object ("presetchoice").get_active()
       self.ProgressBar.set_fraction(0.0)
       if presetchoice == 0:
           self.usingpreset=False
           self.streamdata['devicename'] = "nopreset"
           self.containerchoice.set_sensitive(True)
           self.containerchoice.set_active(0)
           self.start_time = False
           self.streamdata['multipass'] = 0
           self.passcounter = 0
           self.rotationchoice.set_sensitive(True)
           if self.builder.get_object("containerchoice").get_active():
               self.populate_menu_choices()
               self.CodecBox.set_sensitive(True)
               self.transcodebutton.set_sensitive(True)
       else:
           self.usingpreset=True
           self.ProgressBar.set_fraction(0.0)
           if presetchoice != None:
               self.streamdata['devicename']= self.presetchoices[presetchoice-1]
               self.provide_presets(self.streamdata['devicename'])
               self.containerchoice.set_sensitive(False)
               self.CodecBox.set_sensitive(False)
               self.rotationchoice.set_sensitive(False)
           else:
               if self.builder.get_object("containerchoice").get_active_text():
                   self.transcodebutton.set_sensitive(True)

   def on_rotationchoice_changed(self, widget):
       if self.videodata:
           self.videodata[0]['rotationvalue'] = self.rotationchoice.get_active()

   def on_audiocodec_changed(self, widget):
       name=widget.get_name()
       if name.startswith("audiorow"): # this if statement is probably uneeded
          x=name[8:]
          x=int(x)
       self.audiodata[x]['dopassthrough']=False
       if (self.houseclean == False and self.usingpreset==False):
               no=self.audiorows[x].get_active()
               self.audiodata[x]['outputaudiocaps'] = self.audiocodecs[x][no]
               if self.streamdata['container'] != False:
                   if self.audiorows[x].get_active() ==  self.audiopassmenuno:
                       self.audiodata[x]['dopassthrough']= True
               elif self.usingpreset==True:
                   self.audiodata[x]['outputaudiocaps'] = self.presetaudiocodec

   def on_videocodec_changed(self, widget):
       self.videodata[0]['dopassthrough']=False
       if (self.houseclean == False and self.usingpreset==False):
           if self.streamdata['container'] != False:
               no=self.videorows[0].get_active()
               self.videodata[0]['outputvideocaps'] = self.videocodecs[no]
           else:
                   self.videodata[0]['outputvideocaps'] = "novid"
                   self.rotationchoice.set_sensitive(False)
           if self.videorows[0].get_active() == self.videopassmenuno:
               self.videodata[0]['dopassthrough']=True
       elif self.usingpreset==True:
           self.videodata[0]['outputvideocaps'] = self.presetvideocodec


# Setup i18n support
import locale
from gettext import gettext as _
import gettext
import signal
  
#Set up i18n
gettext.bindtextdomain("transmageddon","../../share/locale")
gettext.textdomain("transmageddon")

if __name__ == "__main__":
    app = Transmageddon()
    # FIXME: Get rid of the following line which has the only purpose of
    # working around Ctrl+C not exiting Gtk applications from bug 622084.
    # https://bugzilla.gnome.org/show_bug.cgi?id=622084
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
