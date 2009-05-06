#!/usr/bin/env python

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
import datetime
import codecfinder
import presets

try:
   import gobject; gobject.threads_init()
   import pygst
   import glib
   pygst.require("0.10")
   import gst
except: 
   sys.exit(1)

class Transcoder(gobject.GObject):

   __gsignals__ = {
            'ready-for-querying' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, []),
            'got-eos' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, [])
                    }

   def __init__(self, FILECHOSEN, FILENAME, CONTAINERCHOICE, AUDIOCODECVALUE, VIDEOCODECVALUE):
       gobject.GObject.__init__(self)
       # create a dictionay taking the Codec/Container values and mapping them with plugin names
       # No asfmux atm, hopefully Soc will solve that

       # Choose plugin based on Codec Name
       audiocaps = codecfinder.codecmap[AUDIOCODECVALUE]
       videocaps = codecfinder.codecmap[VIDEOCODECVALUE]
       self.AudioEncoderPlugin = codecfinder.get_audio_encoder_element(audiocaps)
       self.VideoEncoderPlugin = codecfinder.get_video_encoder_element(videocaps)
       # print "Audio encoder plugin is " + self.AudioEncoderPlugin
       # print "Video encoder plugin is " + self.VideoEncoderPlugin

       # Choose plugin and file suffix based on Container name
       containercaps = codecfinder.containermap[CONTAINERCHOICE]
       self.ContainerFormatPlugin = codecfinder.get_muxer_element(containercaps)
       # print "Container muxer is " + self.ContainerFormatPlugin
       self.ContainerFormatSuffix = codecfinder.csuffixmap[CONTAINERCHOICE]

       # Remove suffix from inbound filename so we can reuse it together with suffix to create outbound filename
       self.FileNameOnly = os.path.splitext(os.path.basename(FILENAME))[0]
       self.VideoDirectory = glib.get_user_special_dir(glib.USER_DIRECTORY_VIDEOS)
       CheckDir = os.path.isdir(self.VideoDirectory)
       if CheckDir == (False):
           os.mkdir(self.VideoDirectory)
       # elif CheckDir == (True):
       #   print "Videos directory exist"
       # print self.VideoDirectory

       # create a variable with a timestamp code
       timeget = datetime.datetime.now()
       text = timeget.strftime("-%H%M%S-%d%m%Y") 
       self.timestamp = str(text)

       self.pipeline = gst.Pipeline("TranscodingPipeline")
       self.pipeline.set_state(gst.STATE_PAUSED)

       self.uridecoder = gst.element_factory_make("uridecodebin", "uridecoder")
       self.uridecoder.set_property("uri", FILECHOSEN)
       # print "File loaded " + FILECHOSEN
       self.uridecoder.connect("pad-added", self.OnDynamicPad)
       self.pipeline.add(self.uridecoder)

       self.containermuxer = gst.element_factory_make(self.ContainerFormatPlugin, "containermuxer")
       self.pipeline.add(self.containermuxer)

       self.transcodefileoutput = gst.element_factory_make("filesink", "transcodefileoutput")
       self.transcodefileoutput.set_property("location", (self.VideoDirectory+"/"+self.FileNameOnly+self.timestamp+self.ContainerFormatSuffix))
       self.pipeline.add(self.transcodefileoutput)

       self.containermuxer.link(self.transcodefileoutput)

       self.uridecoder.set_state(gst.STATE_PAUSED)

       self.BusMessages = self.BusWatcher()

       self.uridecoder.connect("no-more-pads", self.noMorePads) # we need to wait on this one before going further

   def noMorePads(self, dbin):
       self.transcodefileoutput.set_state(gst.STATE_PAUSED)
       self.containermuxer.set_state(gst.STATE_PAUSED)
       glib.idle_add(self.idlePlay)
       # print "No More pads received"

   def idlePlay(self):
        self.Pipeline("playing")
        # print "gone to playing"
        return False

   def BusWatcher(self):
       bus = self.pipeline.get_bus()
       bus.add_watch(self.on_message)
       # print bus

   def on_message(self, bus, message):
       mtype = message.type
       #print mtype
       if mtype == gst.MESSAGE_ERROR:
           err, debug = message.parse_error()
           print err 
           print debug
       elif mtype == gst.MESSAGE_ASYNC_DONE:
           self.emit('ready-for-querying')
           # print "Got ASYNC_DONE, setting pipeline to playing"
           # print "emiting 'ready' signal"
       elif mtype == gst.MESSAGE_EOS:
           self.emit('got-eos')
           # print "Emiting 'got-eos' signal"
       return True

   def OnDynamicPad(self, dbin, sink_pad):
       # print "OnDynamicPad for Audio and Video Called!"
       c = sink_pad.get_caps().to_string()
       # print "we got caps " + c
       if c.startswith("audio/"):
           #print "Got an audio cap"
           self.audioconverter = gst.element_factory_make("audioconvert")
           self.pipeline.add(self.audioconverter)

           self.audioencoder = gst.element_factory_make(self.AudioEncoderPlugin)
           self.pipeline.add(self.audioencoder)

           self.gstaudioqueue = gst.element_factory_make("queue")
           self.pipeline.add(self.gstaudioqueue)

           sink_pad.link(self.audioconverter.get_pad("sink"))
           self.audioconverter.link(self.audioencoder)
           self.audioencoder.link(self.gstaudioqueue)
           self.audioconverter.set_state(gst.STATE_PAUSED)
           self.audioencoder.set_state(gst.STATE_PAUSED)
           self.gstaudioqueue.set_state(gst.STATE_PAUSED)
           self.gstaudioqueue.link(self.containermuxer)

       elif c.startswith("video/"):
           # print "Got an video cap"
           self.colorspaceconverter = gst.element_factory_make("ffmpegcolorspace")
           self.pipeline.add(self.colorspaceconverter)

           self.videoencoder = gst.element_factory_make(self.VideoEncoderPlugin)
           self.pipeline.add(self.videoencoder)

           self.gstvideoqueue = gst.element_factory_make("queue")
           self.pipeline.add(self.gstvideoqueue)

           sink_pad.link(self.colorspaceconverter.get_pad("sink"))
           self.colorspaceconverter.link(self.videoencoder)
           self.videoencoder.link(self.gstvideoqueue)
           self.colorspaceconverter.set_state(gst.STATE_PAUSED)
           self.videoencoder.set_state(gst.STATE_PAUSED)
           self.gstvideoqueue.set_state(gst.STATE_PAUSED)

           self.gstvideoqueue.link(self.containermuxer)
       else:
           raise Exception("Got a non-A/V pad!")
           # print "Got a non-A/V pad!"

   def Pipeline (self, state):
       if state == ("playing"):
           self.pipeline.set_state(gst.STATE_PLAYING)
       elif state == ("null"):
           self.pipeline.set_state(gst.STATE_NULL)
