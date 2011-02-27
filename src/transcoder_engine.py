# Transmageddon
# Copyright (C) 2009 Christian Schaller <uraeus@gnome.org>
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This librarmy is distributed in the hope that it will be useful,
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
import codecfinder
import presets

try:
   import gobject; gobject.threads_init()
   import pygst
   import glib
   pygst.require("0.10")
   import gst
except Exception, e:
   print "failed to import required modules"
   print e
   sys.exit(1)

class Transcoder(gobject.GObject):

   __gsignals__ = {
            'ready-for-querying' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, []),
            'got-eos' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, []),
            'got-error' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,))
                    }

   def __init__(self, FILECHOSEN, FILENAME, DESTDIR, CONTAINERCHOICE, AUDIOCODECVALUE, VIDEOCODECVALUE, PRESET, 
                      OHEIGHT, OWIDTH, FRATENUM, FRATEDEN, ACHANNELS, MULTIPASS, PASSCOUNTER, OUTPUTNAME, 
                      TIMESTAMP, ROTATIONVALUE, AUDIOPASSTOGGLE, VIDEOPASSTOGGLE, INTERLACED):
       gobject.GObject.__init__(self)

       # Choose plugin based on Container name
       self.containercaps = codecfinder.containermap[CONTAINERCHOICE]

       # Choose plugin based on Codec Name
       # or switch to remuxing mode if any of the values are set to 'pastr'
       self.stoptoggle=False
       self.audiocaps = AUDIOCODECVALUE
       self.videocaps = VIDEOCODECVALUE
       self.audiopasstoggle = AUDIOPASSTOGGLE
       self.interlaced = INTERLACED
       self.videopasstoggle = VIDEOPASSTOGGLE
       self.doaudio= False
       if self.audiopasstoggle == False:
           self.AudioEncoderPlugin = codecfinder.get_audio_encoder_element(self.audiocaps)
       if self.videopasstoggle == False:
           self.VideoEncoderPlugin = codecfinder.get_video_encoder_element(self.videocaps)
       self.preset = PRESET
       self.oheight = OHEIGHT
       self.owidth = OWIDTH
       self.fratenum = FRATENUM
       self.frateden = FRATEDEN
       self.achannels = ACHANNELS
       # print "transcoder_engine achannels is " + str(self.achannels)
       self.blackborderflag = False
       self.multipass = MULTIPASS
       self.passcounter = PASSCOUNTER
       self.outputfilename = OUTPUTNAME
       self.timestamp = TIMESTAMP
       self.rotationvalue = int(ROTATIONVALUE)
       self.vbox = {}

       # if needed create a variable to store the filename of the multipass statistics file
       if self.multipass != False:
           self.cachefile = (str(glib.get_user_cache_dir())+"/"+"multipass-cache-file"+self.timestamp+".log")

       # Create transcoding pipeline
       self.pipeline = gst.Pipeline("TranscodingPipeline")
       self.pipeline.set_state(gst.STATE_PAUSED)

       self.uridecoder = gst.element_factory_make("uridecodebin", "uridecoder")
       self.uridecoder.set_property("uri", FILECHOSEN)
       self.uridecoder.connect("pad-added", self.OnDynamicPad)

       # self.gstmultiqueue = gst.element_factory_make("multiqueue")
       # self.multiqueueaudiosinkpad = self.gstmultiqueue.get_request_pad("sink0")
       # self.multiqueuevideosinkpad = self.gstmultiqueue.get_request_pad("sink1")
       # self.multiqueueaudiosrcpad = self.gstmultiqueue.get_pad("src0")
       # self.multiqueuevideosrcpad = self.gstmultiqueue.get_pad("src1")

       # self.pipeline.add(self.gstmultiqueue) 

       self.encodebinprofile = gst.pbutils.EncodingContainerProfile ("ogg", None , gst.Caps(self.containercaps), None)
       self.videoprofile = gst.pbutils.EncodingVideoProfile (gst.Caps(self.videocaps), None, gst.caps_new_any(), 0)
       self.audioprofile = gst.pbutils.EncodingAudioProfile (gst.Caps(self.audiocaps), None, gst.caps_new_any(), 0)
       self.encodebinprofile.add_profile(self.videoprofile)
       self.encodebinprofile.add_profile(self.audioprofile)

       self.encodebin = gst.element_factory_make ("encodebin", None)
       self.encodebin.set_property("profile", self.encodebinprofile)
       self.encodebin.set_property("avoid-reencoding", True)
       self.pipeline.add(self.encodebin)

       self.remuxcaps = gst.Caps()
       if self.audiopasstoggle:
          self.remuxcaps.append(self.audiocaps)
       if self.videopasstoggle:
          self.remuxcaps.append(self.videocaps)
       if self.audiopasstoggle and not self.videopasstoggle:
          self.remuxcaps.append_structure(gst.Structure("video/x-raw-rgb"))
          self.remuxcaps.append_structure(gst.Structure("video/x-raw-yuv"))
       if self.videopasstoggle and not self.audiopasstoggle:
          self.remuxcaps.append_structure(gst.Structure("audio/x-raw-float"))
          self.remuxcaps.append_structure(gst.Structure("audio/x-raw-int"))  

       if (self.audiopasstoggle) or (self.videopasstoggle):
           # print "remuxcaps is " + str(self.remuxcaps)
           self.uridecoder.set_property("caps", self.remuxcaps)
       self.pipeline.add(self.uridecoder)

       self.transcodefileoutput = gst.element_factory_make("filesink", "transcodefileoutput")
       self.transcodefileoutput.set_property("location", (DESTDIR+"/"+self.outputfilename))
       self.pipeline.add(self.transcodefileoutput)
       self.encodebin.link(self.transcodefileoutput)

       # print "reached end of first pipeline bulk, next step dynamic audio/video pads"

       if self.rotationvalue == 1 or self.rotationvalue == 3:
           # print "switching height and with around"
           nwidth = height
           nheight = width
           height = nheight
           width = nwidth

       #self.fakesink = gst.element_factory_make("fakesink", "fakesink")
       #self.pipeline.add(self.fakesink) 

       self.uridecoder.set_state(gst.STATE_PAUSED)
       self.encodebin.set_state(gst.STATE_PAUSED)
       # print "setting uridcodebin to paused"
       self.BusMessages = self.BusWatcher()

       self.uridecoder.connect("no-more-pads", self.noMorePads) # we need to wait on this one before going further
       # print "connecting to no-more-pads"

       # Some encoders like x264enc are not able to handle odd height or widths
      # if width % 2:
        #   width += 1
      # if height % 2:
       #    height += 1


       # print "final height " + str(height) + " final width " + str(width)
     #  return height, width, num, denom, pixelaspectratio

   def noMorePads(self, dbin):
       if (self.multipass == False) or (self.passcounter == int(0)):
           self.transcodefileoutput.set_state(gst.STATE_PAUSED)
       glib.idle_add(self.idlePlay)
       # print "No More pads received"

   def idlePlay(self):
        self.Pipeline("playing")
        # print "gone to playing"
        return False

   def BusWatcher(self):
       bus = self.pipeline.get_bus()
       bus.add_watch(self.on_message)

   def on_message(self, bus, message):
       mtype = message.type
       # print mtype
       if mtype == gst.MESSAGE_ERROR:
           err, debug = message.parse_error()
           print err 
           print debug
           gst.DEBUG_BIN_TO_DOT_FILE (self.pipeline, gst.DEBUG_GRAPH_SHOW_ALL, 'transmageddon.dot')
       elif mtype == gst.MESSAGE_ASYNC_DONE:
           self.emit('ready-for-querying')
       elif mtype == gst.MESSAGE_EOS:
           if (self.multipass != False):
               if (self.passcounter == 0):
                   #removing multipass cache file when done
                   if os.access(self.cachefile, os.F_OK):
                       os.remove(self.cachefile)
           self.emit('got-eos')
           self.pipeline.set_state(gst.STATE_NULL)
       elif mtype == gst.MESSAGE_APPLICATION:
           print "I am getting the appliation message"
           self.pipeline.set_state(gst.STATE_NULL)
           self.pipeline.remove(self.uridecoder)
       return True

   def OnDynamicPad(self, uridecodebin, src_pad):
       # c = src_pad.get_caps().to_string()
       sinkpad = self.encodebin.emit("request-pad", src_pad.get_caps())
       c = sinkpad.get_caps().to_string()
       if c.startswith("audio/"):
          src_pad.link(sinkpad)
       elif c.startswith("video/"):
           if self.videopasstoggle==False:
               self.videoflipper = gst.element_factory_make("videoflip")
               self.videoflipper.set_property("method", self.rotationvalue)
               self.pipeline.add(self.videoflipper)
               src_pad.link(self.videoflipper.get_static_pad("sink"))
               self.videoflipper.get_static_pad("src").link(sinkpad)
               self.videoflipper.set_state(gst.STATE_PAUSED)
           else:
               src_pad.link(sinkpad)

   def Pipeline (self, state):
       if state == ("playing"):
           self.pipeline.set_state(gst.STATE_PLAYING)
       elif state == ("null"):
           self.pipeline.set_state(gst.STATE_NULL)
