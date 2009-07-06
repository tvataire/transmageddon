# Transmageddon
# Copyright (C) 2009 Christian Schaller <uraeus@gnome.org>
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



import sys
import os
import time
import transcoder_engine
import gobject; gobject.threads_init()
from urlparse import urlparse
import codecfinder
import about
import presets
import utils
import datetime
import discoverer
from gettext import gettext as _
import gettext

try:
   import pygtk
   pygtk.require("2.0")
   import glib
   import gtk
   import gtk.glade
   import pygst
   pygst.require("0.10")
   import gst
   import gst.pbutils
except:
   print "failed to import required modules"
   sys.exit(1)

major, minor, patch = gobject.pygobject_version
if (major == 2) and (minor < 18):
   print "You need version 2.18.0 or higher of pygobject for Transmageddon" 
   sys.exit(1)

supported_containers = [
        "Ogg",
        "Matroska",
        "AVI",
        "MPEG TS",
        "FLV",
        "Quicktime",
        "MPEG4",
        "3GPP",
        "MXF"
]

supported_audio_codecs = [
       "vorbis",
       "flac",
       "mp3",
       "aac",
       "ac3",
       "speex",
       "celt",
       "amrnb"
#       "alac",
#       "wma2",
]

supported_video_codecs = [
       "theora",
       "dirac",
       "h264",
       "mpeg2",
       "mpeg4",
       "xvid",
       "h263p"
]

# Maps containers to the codecs they support.  The first two elements are
# "special" in that they are the default audio/video selections for that
# container.
supported_container_map = {
    'Ogg':        [ 'vorbis', 'theora', 'flac', 'speex', 'celt', 'dirac' ],
    'MXF':        [ 'mp3', 'h264', 'aac', 'ac3', 'mpeg2', 'mpeg4' ],
    'Matroska':   [ 'flac', 'dirac', 'aac', 'ac3', 'theora', 'mp3', 'h264',
    'mpeg4', 'mpeg2', 'xvid', 'vorbis', 'h263p' ],
    'AVI':        [ 'mp3', 'h264', 'dirac', 'ac3', 'mpeg2', 'mpeg4', 'xvid' ],
    'Quicktime':  [ 'aac', 'h264', 'ac3', 'dirac', 'mp3', 'mpeg2', 'mpeg4' ],
    'MPEG4':      [ 'aac', 'h264', 'mp3', 'mpeg2', 'mpeg4' ],
    '3GPP':       [ 'aac', 'h264', 'mp3', 'mpeg2', 'mpeg4','amrnb','h263p' ],
    'MPEG PS':    [ 'mp3', 'mpeg2', 'ac3', 'h264', 'aac', 'mpeg4' ],
    'MPEG TS':    [ 'mp3', 'h264', 'ac3', 'mpeg2', 'aac', 'mpeg4', 'dirac' ],
    'FLV':        [ 'mp3', 'h264' ],
}

class TransmageddonUI (gtk.glade.XML):
   """This class loads the Glade file of the UI"""
   def __init__(self):
       #Set up i18n
       for module in gtk.glade, gettext:
           module.bindtextdomain("transmageddon","../../share/locale")
           module.textdomain("transmageddon")

       #Set the Glade file
       self.gladefile = "transmageddon.glade"
       gtk.glade.XML.__init__ (self, self.gladefile)

       #Define functionality of our button and main window
       self.TopWindow = self.get_widget("TopWindow")
       self.FileChooser = self.get_widget("FileChooser")
       self.videoinformation = self.get_widget("videoinformation")
       self.audioinformation = self.get_widget("audioinformation")
       self.videocodec = self.get_widget("videocodec")
       self.audiocodec = self.get_widget("audiocodec")
       self.CodecBox = self.get_widget("CodecBox")
       self.presetchoice = self.get_widget("presetchoice")
       self.containerchoice = self.get_widget("containerchoice")
       self.rotationchoice = self.get_widget("rotationchoice")
       self.codec_buttons = dict()
       for c in supported_audio_codecs:
           self.codec_buttons[c] = self.get_widget(c+"button")
           self.codec_buttons[c].connect("clicked",
                                         self.on_audiobutton_pressed, c)
       for c in supported_video_codecs:
           self.codec_buttons[c] = self.get_widget(c+"button")
           self.codec_buttons[c].connect("clicked",
                                         self.on_videobutton_pressed, c)

       self.transcodebutton = self.get_widget("transcodebutton")
       self.ProgressBar = self.get_widget("ProgressBar")
       self.cancelbutton = self.get_widget("cancelbutton")
       self.StatusBar = self.get_widget("StatusBar")

       self.TopWindow.connect("destroy", gtk.main_quit)

       self.signal_autoconnect(self) # Initialize User Interface

       self.start_time = False
       self.multipass = False
       self.passcounter = False
       
       # Set the Videos XDG UserDir as the default directory for the filechooser, 
       # also make sure directory exists
       if 'get_user_special_dir' in glib.__dict__:
           self.videodirectory = glib.get_user_special_dir(glib.USER_DIRECTORY_VIDEOS)
       else:
            print "XDG video directory not available"
            self.videodirectory = os.getenv('HOME')

       CheckDir = os.path.isdir(self.videodirectory)
       if CheckDir == (False):
           os.mkdir(self.videodirectory)
       self.FileChooser.set_current_folder(self.videodirectory)

       # Setting AppIcon
       FileExist = os.path.isfile("../../share/pixmaps/transmageddon.png")
       if FileExist:
           self.TopWindow.set_icon_from_file("../../share/pixmaps/transmageddon.png")
       else:
           try:
               self.TopWindow.set_icon_from_file("transmageddon.png")
           except:
               print "failed to find appicon"

       # default all but top box to insensitive by default
       # self.containerchoice.set_sensitive(False)
       self.CodecBox.set_sensitive(False)
       self.transcodebutton.set_sensitive(False)
       self.cancelbutton.set_sensitive(False)
       self.presetchoice.set_sensitive(False)
       self.containerchoice.set_sensitive(False)
       self.rotationchoice.set_sensitive(False)

       # set default values for various variables
       self.AudioCodec = "vorbis"
       self.VideoCodec = "theora"
       self.ProgressBar.set_text(_("Transcoding Progress"))

       self.p_duration = gst.CLOCK_TIME_NONE
       self.p_time = gst.FORMAT_TIME

       # Populate the Container format combobox
       self.lst = supported_containers
       for i in self.lst:
           self.containerchoice.append_text(i)

       # Populate the rotatation box
       self.rotationlist = ["No rotation (default)", "Clockwise 90 degrees", "Rotate 180 degrees", 
                           "Counterclockwise 90 degrees", "Horizontal flip", 
                           "Vertical flip", "Upper left diagonal flip", 
                           "Upper right diagnonal flip" ]
       for y in self.rotationlist: 
           self.rotationchoice.append_text(y)

       self.rotationchoice.set_active(0)
       self.rotationvalue == int(0) 
      
       # Populate Device Presets combobox
       devicelist = []
       shortname = []
       for x, (name, device) in enumerate(sorted(presets.get().items(),
                                   lambda x, y: cmp(x[1].make + x[1].model,
                                                    y[1].make + y[1].model))):
           iter = self.presetchoice.append_text(str(device))
           devicelist.append(str(device))
           shortname.append(str(name))

       #for (name, device) in (presets.get().items()):
       #    shortname.append(str(name))
       self.presetchoices = dict(zip(devicelist, shortname))     
       self.presetchoice.prepend_text("No Presets")

       self.waiting_for_signal="False"

   # Get all preset values
   def reverse_lookup(self,v):
    for k in codecfinder.codecmap:
        if codecfinder.codecmap[k] == v:
            return k

   def provide_presets(self,devicename): 
       devices = presets.get()
       device = devices[devicename]
       preset = device.presets["Normal"]
       if preset.container == "application/ogg":
           self.containerchoice.set_active(0)
       elif preset.container == "video/x-matroska":
           self.containerchoice.set_active(1)
       elif preset.container == "video/x-msvideo":
           self.containerchoice.set_active(2)
       elif preset.container == "video/mpegts":
           self.containerchoice.set_active(3)
       elif preset.container == "video/x-flv":
           self.containerchoice.set_active(4)
       elif preset.container == "video/quicktime,variant=apple":
           self.containerchoice.set_active(5)
       elif preset.container == "video/quicktime,variant=iso":
           self.containerchoice.set_active(6)
       elif preset.container == "video/quicktime,variant=3gpp":
           self.containerchoice.set_active(7)
       elif preset.container == "video/quicktime,variant=3gpp":
           self.containerchoice.set_active(8)
       elif preset.container == "application/mxf":
           self.containerchoice.set_active(9) 
       else:
            print "failed to set container format"
       # print preset.acodec.name
       self.codec_buttons[self.reverse_lookup(str(preset.acodec.name))].set_active(True)
       self.codec_buttons[self.reverse_lookup(str(preset.vcodec.name))].set_active(True)


       # Check for number of passes
       passes = preset.vcodec.passes
       if passes == "0":
          self.multipass = False
       else:
          self.multipass = int(passes)
          self.passcounter = int(0)

   # Create query on uridecoder to get values to populate progressbar 
   # Notes:
   # Query interface only available on uridecoder, not decodebin2)
   # FORMAT_TIME only value implemented by all plugins used
   # a lot of original code from gst-python synchronizer.py example
   def Increment_Progressbar(self):
       if self.start_time == False:  
           self.start_time = time.time()
       try:
           position, format = self._transcoder.uridecoder.query_position(gst.FORMAT_TIME)
       except:
           position = gst.CLOCK_TIME_NONE

       try:
           duration, format = self._transcoder.uridecoder.query_duration(gst.FORMAT_TIME)
       except:
           duration = gst.CLOCK_TIME_NONE
       if position != gst.CLOCK_TIME_NONE:
           value = float(position) / duration
           if float(value) < (1.0) and float(value) >= 0:
               self.ProgressBar.set_fraction(value)
               percent = (value*100)
               timespent = time.time() - self.start_time
               percent_remain = (100-percent)
               # print percent_remain
               rem = (timespent / percent) * percent_remain
               min = rem / 60
               sec = rem % 60
               time_rem = _("%(min)d:%(sec)02d") % {
                   "min": min,
                   "sec": sec,
                   }
               if percent_remain > 0.5:
                   if self.passcounter == int(0):
                       self.ProgressBar.set_text(_("Estimated time remaining: ") + str(time_rem))
                   else:
                       self.ProgressBar.set_text(_("Pass " + str(self.passcounter) + " time remaining: ") + str(time_rem))
               return True
           else:
               self.ProgressBar.set_fraction(0.0)
               return False
       else:
           return False

   # Call gobject.timeout_add with a value of 500millisecond to regularly poll for position so we can
   # use it for the progressbar
   def ProgressBarUpdate(self, source):
       gobject.timeout_add(500, self.Increment_Progressbar)
       # print "ProgressBar timeout_add startet"


   # Set up function to start listening on the GStreamer bus
   # We need this so we know when the pipeline has started and when the pipeline has stopped
   # listening for ASYNC_DONE is sorta ok way to listen for when the pipeline is running
   # You need to listen on the GStreamer bus to know when EOS is hit for instance.

   def _on_eos(self, source):
       context_id = self.StatusBar.get_context_id("EOS")
       if (self.multipass ==  False) or (self.passcounter == int(0)):
           self.StatusBar.push(context_id, (_("File saved to ") + self.videodirectory))
           self.FileChooser.set_sensitive(True)
           self.containerchoice.set_sensitive(True)
           self.CodecBox.set_sensitive(True)
           self.presetchoice.set_sensitive(True)
           self.cancelbutton.set_sensitive(False)
           self.transcodebutton.set_sensitive(False)
           self.rotationchoice.set_sensitive(True)
           self.start_time = False
           self.ProgressBar.set_text(_("Done Transcoding"))
           self.ProgressBar.set_fraction(1.0)
           self.start_time = False
           self.multipass = False
           self.passcounter = False
       else:
           self.StatusBar.push(context_id, (_("Pass " + str(self.passcounter) + " Complete")))
           self.start_time = False
           self.ProgressBar.set_text(_("Start next pass"))
           if self.passcounter == (self.multipass-1):
               self.passcounter = int(0)
               self._start_transcoding()
           else:
               self.passcounter = self.passcounter+1
               self._start_transcoding()


   # Use the pygst extension 'discoverer' to get information about the incoming media. Probably need to get codec data in another way.
   # this code is probably more complex than it needs to be currently
 
   def succeed(self, d):
       if d.is_video:
           self.videodata = { 'videowidth' : d.videowidth, 'videoheight' : d.videoheight, 'videotype' : d.inputvideocaps,
                              'videolenght' : d.videolength, 'fratenum' : d.videorate.num, 'frateden' :  d.videorate.denom }
           self.videoinformation.set_markup(''.join(('<small>', 'Video height&#47;width: ', str(self.videodata['videoheight']), 
                                            "x", str(self.videodata['videowidth']), '</small>')))
           self.videocodec.set_markup(''.join(('<small>', 'Video codec: ', str(gst.pbutils.get_codec_description(self.videodata['videotype'])), '</small>')))
       if d.is_audio:
           self.audiodata = { 'audiochannels' : d.audiochannels, 'samplerate' : d.audiorate, 'audiotype' : d.inputaudiocaps }
           self.audioinformation.set_markup(''.join(('<small>', 'Audio channels: ', str(self.audiodata['audiochannels']), '</small>')))
           self.audiocodec.set_markup(''.join(('<small>','Audio codec: ',str(gst.pbutils.get_codec_description(self.audiodata['audiotype'])),'</small>')))
       if self.waiting_for_signal == "True":
           self.check_for_elements()

   def discover(self, path):
       self.videodata ={}
       def discovered(d, is_media):
           if is_media:
               self.succeed(d)
       d = discoverer.Discoverer(path)
       d.connect('discovered', discovered)
       d.discover()

   def mediacheck(self, FileChosen):
       uri = urlparse (FileChosen)
       path = uri.path
       # print path
       return self.discover(path)

   # define the behaviour of the other buttons
   def on_FileChooser_file_set(self, widget):
       self.filename = self.get_widget ("FileChooser").get_filename()
       self.audiodata = {}
       codecinfo = self.mediacheck(self.filename)
       self.containerchoice.set_sensitive(True)
       self.presetchoice.set_sensitive(True)
       self.presetchoice.set_active(0)
       self.ProgressBar.set_fraction(0.0)
       self.ProgressBar.set_text(_("Transcoding Progress"))

   def _start_transcoding(self): 
       filechoice = self.get_widget ("FileChooser").get_uri()
       self.filename = self.get_widget ("FileChooser").get_filename()
       vheight = self.videodata['videoheight']
       vwidth = self.videodata['videowidth']
       ratenum = self.videodata['fratenum']
       ratednom = self.videodata['frateden']
       achannels = self.audiodata['audiochannels']
       container = self.get_widget ("containerchoice").get_active_text ()
       self._transcoder = transcoder_engine.Transcoder(filechoice, self.filename, self.videodirectory, container, 
                                                       self.AudioCodec, self.VideoCodec, self.devicename, 
                                                       vheight, vwidth, ratenum, ratednom, achannels, 
                                                       self.multipass, self.passcounter, self.outputfilename,
                                                       self.timestamp, self.rotationvalue)
       
       self._transcoder.connect("ready-for-querying", self.ProgressBarUpdate)
       self._transcoder.connect("got-eos", self._on_eos)
       return True


   def donemessage(self, donemessage, null):
       if donemessage == gst.pbutils.INSTALL_PLUGINS_SUCCESS:
           # print "success " + str(donemessage)
           if gst.update_registry():
               print "Plugin registry updated, trying again"
           else:
               print "GStreamer registry update failed"
           self._start_transcoding()
       elif donemessage == gst.pbutils.INSTALL_PLUGINS_PARTIAL_SUCCESS:
           #print "partial success " + str(donemessage)
           self.check_for_elements()
       elif donemessage == gst.pbutils.INSTALL_PLUGINS_NOT_FOUND:
           # print "not found " + str(donemessage)
           context_id = self.StatusBar.get_context_id("EOS")
           self.StatusBar.push(context_id, _("Plugins not found, choose different codecs."))
           self.FileChooser.set_sensitive(True)
           self.containerchoice.set_sensitive(True)
           self.CodecBox.set_sensitive(True)
           self.cancelbutton.set_sensitive(False)
           self.transcodebutton.set_sensitive(True)
       elif donemessage == gst.pbutils.INSTALL_PLUGINS_USER_ABORT:
           context_id = self.StatusBar.get_context_id("EOS")
           self.StatusBar.push(context_id, _("Codec installation aborted."))
           self.FileChooser.set_sensitive(True)
           self.containerchoice.set_sensitive(True)
           self.CodecBox.set_sensitive(True)
           self.cancelbutton.set_sensitive(False)
           self.transcodebutton.set_sensitive(True)
       else:
           context_id = self.StatusBar.get_context_id("EOS")
           self.StatusBar.push(context_id, _("Missing plugin installation failed: ")) + gst.pbutils.InstallPluginsReturn()

   def check_for_elements(self):
       containerchoice = self.get_widget ("containerchoice").get_active_text ()
       containerstatus = codecfinder.get_muxer_element(codecfinder.containermap[containerchoice])
       audiostatus = codecfinder.get_audio_encoder_element(codecfinder.codecmap[self.AudioCodec])
       videostatus = codecfinder.get_video_encoder_element(codecfinder.codecmap[self.VideoCodec])
       
       if not containerstatus or not videostatus or not audiostatus:
           fail_info = []  
           if containerstatus == False: 
               fail_info.append(gst.caps_from_string(codecfinder.containermap[containerchoice]))
           if audiostatus == False:
               fail_info.append(gst.caps_from_string(codecfinder.codecmap[self.AudioCodec]))
           if videostatus == False:
               fail_info.append(gst.caps_from_string (codecfinder.codecmap[self.VideoCodec]))
           missing = []
           for x in fail_info:
               missing.append(gst.pbutils.missing_encoder_installer_detail_new(x))
           context = gst.pbutils.InstallPluginsContext ()
           gst.pbutils.install_plugins_async (missing, context, self.donemessage, "")
       else:
           self._start_transcoding()

   # The transcodebutton is the one that calls the Transcoder class and thus starts the transcoding
   def on_transcodebutton_clicked(self, widget):
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
       self.timestamp = str(timeget.strftime("-%H%M%S-%d%m%Y"))
       # Remove suffix from inbound filename so we can reuse it together with suffix to create outbound filename
       self.nosuffix = os.path.splitext(os.path.basename(self.filename))[0]
       # pick output suffix
       container = self.get_widget ("containerchoice").get_active_text ()
       self.ContainerFormatSuffix = codecfinder.csuffixmap[container]
       self.outputfilename = str(self.nosuffix+self.timestamp+self.ContainerFormatSuffix)
       context_id = self.StatusBar.get_context_id("EOS")
       self.StatusBar.push(context_id, (_("Writing " + self.outputfilename)))
       if self.multipass == False:
           self.ProgressBar.set_text(_("Transcoding Progress"))
       else:
           self.passcounter=int(1)
           self.ProgressBar.set_text(_("Pass " + str(self.passcounter) + " Progress"))
       if self.audiodata.has_key("samplerate"):
           self.check_for_elements()
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
       self._cancel_encoding = transcoder_engine.Transcoder.Pipeline(self._transcoder,"null")
       self.ProgressBar.set_fraction(0.0)
       self.ProgressBar.set_text(_("Transcoding Progress"))
       context_id = self.StatusBar.get_context_id("EOS")
       self.StatusBar.pop(context_id)

   def on_containerchoice_changed(self, widget):
       self.CodecBox.set_sensitive(True)
       self.rotationchoice.set_sensitive(True)
       self.ProgressBar.set_fraction(0.0)
       self.ProgressBar.set_text(_("Transcoding Progress"))
       containerchoice = self.get_widget ("containerchoice").get_active_text ()
       codecs = supported_container_map[containerchoice]
       self.AudioCodec = codecs[0]
       self.VideoCodec = codecs[1]
       self.transcodebutton.set_sensitive(True)
       for b in self.codec_buttons.values():
           b.set_sensitive(False)
       for c in codecs:
           self.codec_buttons[c].set_sensitive(True)
       self.codec_buttons[self.AudioCodec].set_active(True)
       self.codec_buttons[self.VideoCodec].set_active(True)

   def on_presetchoice_changed(self, widget):
       presetchoice = self.get_widget ("presetchoice").get_active_text ()
       self.ProgressBar.set_fraction(0.0)
       if presetchoice == "No Presets":
           self.devicename = "nopreset"
           self.containerchoice.set_sensitive(True)
           self.start_time = False
           self.multipass = False
           self.passcounter = False
           self.rotationchoice.set_sensitive(True)
           if self.get_widget("containerchoice").get_active_text():
               self.CodecBox.set_sensitive(True)
               self.transcodebutton.set_sensitive(True)
       else:
           self.ProgressBar.set_fraction(0.0)
           self.devicename= self.presetchoices[presetchoice]
           self.provide_presets(self.devicename)
           self.containerchoice.set_sensitive(False)
           self.CodecBox.set_sensitive(False)
           self.rotationchoice.set_sensitive(False)
           if self.get_widget("containerchoice").get_active_text():
               self.transcodebutton.set_sensitive(True)

   def on_rotationchoice_changed(self, widget):
       self.rotationvalue = self.rotationchoice.get_active()
       # print "rotationchoice value " + str(self.rotationvalue)

   def audio_codec_changed (self, audio_codec):
       self.transcodebutton.set_sensitive(True)
       self.AudioCodec = audio_codec

   def video_codec_changed (self, video_codec):
       self.transcodebutton.set_sensitive(True)
       self.VideoCodec = video_codec

   def on_audiobutton_pressed(self, widget, codec):
       self.AudioCodec = codec

   def on_videobutton_pressed(self, widget, codec):
       self.VideoCodec = codec

   def on_about_dialog_activate(self, widget):
       """
           Show the about dialog.
       """
       about.AboutDialog()

if __name__ == "__main__":
        hwg = TransmageddonUI()
        gtk.main()


