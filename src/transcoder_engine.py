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

   def __init__(self, FILECHOSEN, FILENAME, CONTAINERCHOICE, AUDIOCODECVALUE, VIDEOCODECVALUE, PRESET, 
                      OHEIGHT, OWIDTH, FRATENUM, FRATEDEN):
       gobject.GObject.__init__(self)

       # Choose plugin and file suffix based on Container name
       containercaps = codecfinder.containermap[CONTAINERCHOICE]
       self.ContainerFormatPlugin = codecfinder.get_muxer_element(containercaps)
       # print "Container muxer is " + self.ContainerFormatPlugin
       self.ContainerFormatSuffix = codecfinder.csuffixmap[CONTAINERCHOICE]

       # Choose plugin based on Codec Name
       self.audiocaps = codecfinder.codecmap[AUDIOCODECVALUE]
       videocodecvalue = VIDEOCODECVALUE
       self.videocaps = codecfinder.codecmap[videocodecvalue]
       # print "videocaps ended up as " + str(self.videocaps)
       self.AudioEncoderPlugin = codecfinder.get_audio_encoder_element(self.audiocaps)
       self.VideoEncoderPlugin = codecfinder.get_video_encoder_element(self.videocaps)

       self.preset = PRESET
       self.oheight = OHEIGHT
       self.owidth = OWIDTH
       self.fratenum = FRATENUM
       self.frateden = FRATEDEN
       self.blackborderflag = False
       self.vbox = {}

       # Remove suffix from inbound filename so we can reuse it together with suffix to create outbound filename
       self.FileNameOnly = os.path.splitext(os.path.basename(FILENAME))[0]
       self.VideoDirectory = glib.get_user_special_dir(glib.USER_DIRECTORY_VIDEOS)
       CheckDir = os.path.isdir(self.VideoDirectory)
       if CheckDir == (False):
           os.mkdir(self.VideoDirectory)
       # elif CheckDir == (True):
       # print "Videos directory exist"
       # print self.VideoDirectory     

       # create a variable with a timestamp code
       timeget = datetime.datetime.now()
       text = timeget.strftime("-%H%M%S-%d%m%Y") 
       self.timestamp = str(text)

       self.pipeline = gst.Pipeline("TranscodingPipeline")
       self.pipeline.set_state(gst.STATE_PAUSED)

       self.uridecoder = gst.element_factory_make("uridecodebin", "uridecoder")
       self.uridecoder.set_property("uri", FILECHOSEN)
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

   # Get hold of all needed data from the XML profile files. 
   def provide_presets(self):
       devices = presets.get()
       device = devices[self.preset]
       preset = device.presets["Normal"]
       
       # Check for black border boolean
       border = preset.vcodec.border
       if border == "Y":
           self.blackborderflag = True
       else:
           self.blackborderflag = False
           print "border flag set to False"

       # Check for audio samplerate
       self.samplerate = int(preset.acodec.samplerate)
       chanmin, chanmax = preset.acodec.channels
       self.channels = int(chanmax)
       print "channels " + str(self.channels)
       
       # Check if rescaling is needed and calculate new video width/height keeping aspect ratio
       # Also add black borders if needed
       wmin, wmax  =  preset.vcodec.width
       hmin, hmax = preset.vcodec.height
       width, height = self.owidth, self.oheight
       self.vpreset = []       
       voutput = preset.vcodec.passes[0].split(", ")
       for x in voutput:
           self.vpreset.append(x)
       self.apreset = []
       aoutput = preset.acodec.passes[0].split(", ")
       for x in aoutput:
           self.apreset.append(x)
       # Scale width / height down
       if self.owidth > wmax:
           # print "output video smaller than input video, scaling"
           width = wmax
           height = int((float(wmax) / self.owidth) * self.oheight)
       if height > hmax:
           height = hmax
           width = int((float(hmax) / self.oheight) * self.owidth)
       # Some encoders like x264enc are not able to handle odd height or widths
       if width % 2:
           width += 1
       if height % 2:
           height += 1
       print "scaled output size " + str(height) + " " + str(width)

       # Add any required padding
       if self.blackborderflag == True:
           print "blackborderflag == True"
           print "width: " + str(width) + " height: " + str(height)
           print "wmin: " + str(wmin) + " hmin: " + str(hmin) 
           if width < wmin and height < hmin:
               print "both borders"
               wpx = (wmin - width) / 2
               hpx = (hmin - height) / 2
               self.vbox['left'] = wpx
               self.vbox['right'] = wpx
               self.vbox['top'] = hpx
               self.vbox['bottom'] = hpx
           elif width < wmin:
               print "side borders"
               px = (wmin - width) / 2
               self.vbox['left'] = px
               self.vbox['right'] = px
               self.vbox['top'] = 0
               self.vbox['bottom'] = 0
           elif height < hmin:
               print "top/bottom borders"
               px = (hmin - height) / 2
               self.vbox['top'] = px
               self.vbox['bottom'] = px
               self.vbox['left'] = int(0)
               self.vbox['right'] = int(0)

           print "vbox is " + str(self.vbox)

       # Setup video framerate and add to caps - 
       # FIXME: Is minimum framerate really worthwhile checking for?
       # =================================================================
       rmin = preset.vcodec.rate[0].num / \
           float(preset.vcodec.rate[0].denom)
       print "rmin er " + str(rmin)
       rmax = preset.vcodec.rate[1].num / \
           float(preset.vcodec.rate[1].denom)
       print "rmax er " + str(rmax)
       orate = self.fratenum / self.frateden
            
       if orate > rmax:
           num = preset.vcodec.rate[1].num
           denom = preset.vcodec.rate[1].denom
       elif orate < rmin:
           num = preset.vcodec.rate[0].num
           denom = preset.vcodec.rate[0].denom
       else:
           num = self.fratenum
           denom = self.frateden


       return height, width, num, denom

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
       # print mtype
       if mtype == gst.MESSAGE_ERROR:
           err, debug = message.parse_error()
           print err 
           print debug
       elif mtype == gst.MESSAGE_ASYNC_DONE:
           self.emit('ready-for-querying')
           # print "emiting 'ready' signal"
       elif mtype == gst.MESSAGE_EOS:
           self.emit('got-eos')
           print "Emiting 'got-eos' signal"
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
           if self.preset != "nopreset":
               GstPresetType = gobject.type_from_name("GstPreset")
               if GstPresetType in gobject.type_interfaces(self.audioencoder):
                   print "testing for interface"
                   for x in self.apreset:
                       mandy = self.audioencoder.load_preset(x)
                       print "Audio preset is getting set " + str(mandy)
                       print "and the name of preset is " + str(x)

               self.audioresampler = gst.element_factory_make("audioresample")
               self.pipeline.add(self.audioresampler)

               self.acaps = gst.Caps()
               self.acaps.append_structure(gst.Structure("audio/x-raw-float"))
               self.acaps.append_structure(gst.Structure("audio/x-raw-int"))
               for acap in self.acaps:
                   acap["rate"] = self.samplerate
                   acap["channels"] = self.channels
               
               print self.acaps
               self.acapsfilter = gst.element_factory_make("capsfilter")
               self.acapsfilter.set_property("caps", self.acaps)
               self.pipeline.add(self.acapsfilter)
                   
           self.gstaudioqueue = gst.element_factory_make("queue")
           self.pipeline.add(self.gstaudioqueue)

           sink_pad.link(self.audioconverter.get_pad("sink"))
           if self.preset != "nopreset":
               self.audioconverter.link(self.audioresampler)
               self.audioresampler.link(self.acapsfilter)
               self.acapsfilter.link(self.audioencoder)
           else:
               self.audioconverter.link(self.audioencoder) 
           self.audioencoder.link(self.gstaudioqueue)
           self.audioconverter.set_state(gst.STATE_PAUSED)
           if self.preset != "nopreset":
               self.audioresampler.set_state(gst.STATE_PAUSED)
               self.acapsfilter.set_state(gst.STATE_PAUSED)
           self.audioencoder.set_state(gst.STATE_PAUSED)
           self.gstaudioqueue.set_state(gst.STATE_PAUSED)
           self.gstaudioqueue.link(self.containermuxer)

       elif c.startswith("video/"):
           # print "Got an video cap"
           self.colorspaceconverter = gst.element_factory_make("ffmpegcolorspace")
           self.pipeline.add(self.colorspaceconverter)
           
           if self.preset != "nopreset":
               self.colorspaceconvert2 = gst.element_factory_make("ffmpegcolorspace")
               self.pipeline.add(self.colorspaceconvert2)
           
               self.vcaps = gst.Caps()
               self.vcaps.append_structure(gst.Structure("video/x-raw-rgb"))
               self.vcaps.append_structure(gst.Structure("video/x-raw-yuv"))
               height, width, num, denom = self.provide_presets()
               for vcap in self.vcaps:
                   vcap["width"] = width
                   vcap["height"] = height
                   vcap["framerate"] = gst.Fraction(num, denom)
               print self.vcaps

               self.vcapsfilter = gst.element_factory_make("capsfilter")
               self.vcapsfilter.set_property("caps", self.vcaps)
               self.pipeline.add(self.vcapsfilter)

               
               self.videorate = gst.element_factory_make("videorate", "videorate")
               self.pipeline.add(self.videorate)

               self.videoscaler = gst.element_factory_make("videoscale", "videoscaler")
               self.videoscaler.set_property("method", int(1))
               self.pipeline.add(self.videoscaler)
               if self.blackborderflag == True:
                   self.videoboxer = gst.element_factory_make("videobox", "videoboxer")
                   self.videoboxer.set_property("top", self.vbox["top"])
                   self.videoboxer.set_property("bottom", self.vbox["bottom"])
                   self.videoboxer.set_property("right", self.vbox["right"])
                   self.videoboxer.set_property("left", self.vbox["left"])
                   self.pipeline.add(self.videoboxer)

           print self.videocaps
           self.vcapsfilter2 = gst.element_factory_make("capsfilter")
           caps = gst.caps_from_string(self.videocaps)
           printcaps = gst.Caps.to_string(caps)
           print "generated caps from string " + str(printcaps)
           self.vcapsfilter2.set_property("caps", caps)
           print self.vcapsfilter2
           self.pipeline.add(self.vcapsfilter2)

           self.videoencoder = gst.element_factory_make(self.VideoEncoderPlugin)
           self.pipeline.add(self.videoencoder)
           if self.preset != "nopreset":
               GstPresetType = gobject.type_from_name("GstPreset")
               if GstPresetType in gobject.type_interfaces(self.videoencoder):
                   print "testing for interface"
                   for x in self.vpreset:
                       bob = self.videoencoder.load_preset(x)
                       print "preset is getting set " + str(bob)
                       print "and the name of preset is " + str(x)
           self.gstvideoqueue = gst.element_factory_make("queue")
           self.pipeline.add(self.gstvideoqueue)

           sink_pad.link(self.colorspaceconverter.get_pad("sink"))
           if self.preset != "nopreset":
               self.colorspaceconverter.link(self.videoscaler)
               self.videoscaler.link(self.videorate)
               self.videorate.link(self.vcapsfilter)
               if self.blackborderflag == True:
                   self.vcapsfilter.link(self.videoboxer)
                   self.videoboxer.link(self.colorspaceconvert2)
               else:
                   self.vcapsfilter.link(self.colorspaceconvert2)
               self.colorspaceconvert2.link(self.videoencoder)
           else:
               self.colorspaceconverter.link(self.videoencoder)
               
               
           self.videoencoder.link(self.vcapsfilter2)
           self.vcapsfilter2.link(self.gstvideoqueue)
           self.colorspaceconverter.set_state(gst.STATE_PAUSED)
           if self.preset != "nopreset":
               self.videoscaler.set_state(gst.STATE_PAUSED)
               self.videorate.set_state(gst.STATE_PAUSED)
               self.vcapsfilter.set_state(gst.STATE_PAUSED)
               if self.blackborderflag == True:
                   self.videoboxer.set_state(gst.STATE_PAUSED)
               self.colorspaceconvert2.set_state(gst.STATE_PAUSED)
           self.vcapsfilter2.set_state(gst.STATE_PAUSED)
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
