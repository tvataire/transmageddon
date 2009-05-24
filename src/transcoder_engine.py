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
                      OHEIGHT, OWIDTH, FRATENUM, FRATEDEN, ACHANNELS, MULTIPASS, PASSCOUNTER, OUTPUTNAME, 
                      TIMESTAMP):
       gobject.GObject.__init__(self)

       # Choose plugin based on Container name
       containercaps = codecfinder.containermap[CONTAINERCHOICE]
       self.ContainerFormatPlugin = codecfinder.get_muxer_element(containercaps)

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
       self.achannels = ACHANNELS
       self.blackborderflag = False
       self.multipass = MULTIPASS
       self.passcounter = PASSCOUNTER
       self.outputfilename = OUTPUTNAME
       self.timestamp = TIMESTAMP
       self.vbox = {}
       print "Passcounter is " + str(self.passcounter)

       self.VideoDirectory = glib.get_user_special_dir(glib.USER_DIRECTORY_VIDEOS)
       CheckDir = os.path.isdir(self.VideoDirectory)
       if CheckDir == (False):
           os.mkdir(self.VideoDirectory)
       # elif CheckDir == (True):
       # print "Videos directory exist"
       # print self.VideoDirectory     

       # if needed create a variable to store the filename of the multipass statistics file
       if self.multipass != False:
           self.cachefilename = ("multipass-cache-file"+self.timestamp+".log")
           print self.cachefilename

       # Create transcoding pipeline
       self.pipeline = gst.Pipeline("TranscodingPipeline")
       self.pipeline.set_state(gst.STATE_PAUSED)

       self.uridecoder = gst.element_factory_make("uridecodebin", "uridecoder")
       self.uridecoder.set_property("uri", FILECHOSEN)
       self.uridecoder.connect("pad-added", self.OnDynamicPad)
       self.pipeline.add(self.uridecoder)
       
       if (self.multipass == False) or (self.passcounter == int(0)):
           print "creating muxer and filesink since multipass is " + str(self.multipass)
           self.containermuxer = gst.element_factory_make(self.ContainerFormatPlugin, "containermuxer")
           self.pipeline.add(self.containermuxer)

           self.transcodefileoutput = gst.element_factory_make("filesink", "transcodefileoutput")
           self.transcodefileoutput.set_property("location", (self.VideoDirectory+"/"+self.outputfilename))
           self.pipeline.add(self.transcodefileoutput)

           self.containermuxer.link(self.transcodefileoutput)
       else:
           print "creating fakesink since multipass is " + str(self.multipass)
           self.multipassfakesink = gst.element_factory_make("fakesink", "multipassfakesink")
           self.pipeline.add(self.multipassfakesink)    

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

       # Check for audio samplerate
       self.samplerate = int(preset.acodec.samplerate)

       # calculate number of channels
       chanmin, chanmax = preset.acodec.channels
       if int(self.achannels) < int(chanmax):
           if int(self.achannels) > int(chanmin): 
               self.channels = int(self.achannels)
           else:
               self.channels = int(chanmin)
       else:
           self.channels = int(chanmax)
       
       # Check if rescaling is needed and calculate new video width/height keeping aspect ratio
       # Also add black borders if needed
       wmin, wmax  =  preset.vcodec.width
       hmin, hmax = preset.vcodec.height
       width, height = self.owidth, self.oheight
       self.vpreset = []       
       voutput = preset.vcodec.presets[0].split(", ")
       for x in voutput:
           self.vpreset.append(x)
       self.apreset = []
       aoutput = preset.acodec.presets[0].split(", ")
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

       # Add any required padding
       if self.blackborderflag == True: 
           if width < wmin and height < hmin:
               wpx = (wmin - width) / 2
               hpx = (hmin - height) / 2
               self.vbox['left'] = -wpx
               self.vbox['right'] = -wpx
               self.vbox['top'] = -hpx
               self.vbox['bottom'] = -hpx
           elif width < wmin:
               px = (wmin - width) / 2
               self.vbox['left'] = -px
               self.vbox['right'] = -px
               self.vbox['top'] = -0
               self.vbox['bottom'] = -0
           elif height < hmin:
               px = (hmin - height) / 2
               self.vbox['top'] = -px
               self.vbox['bottom'] = -px
               self.vbox['left'] = -int(0)
               self.vbox['right'] = -int(0)

       # Setup video framerate and add to caps - 
       # FIXME: Is minimum framerate really worthwhile checking for?
       # =================================================================
       rmin = preset.vcodec.rate[0].num / \
           float(preset.vcodec.rate[0].denom)
       rmax = preset.vcodec.rate[1].num / \
           float(preset.vcodec.rate[1].denom)
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
       if (self.multipass == False) or (self.passcounter == int(0)):
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
   
   def on_message(self, bus, message):
       mtype = message.type
       if mtype == gst.MESSAGE_ERROR:
           err, debug = message.parse_error()
           print err 
           print debug
       elif mtype == gst.MESSAGE_ASYNC_DONE:
           self.emit('ready-for-querying')
           # print "emiting 'ready' signal"
       elif mtype == gst.MESSAGE_EOS:
           self.emit('got-eos')
           self.pipeline.set_state(gst.STATE_NULL)
           # print "Emiting 'got-eos' signal"
       return True

   def OnDynamicPad(self, dbin, sink_pad):
       c = sink_pad.get_caps().to_string()
       if c.startswith("audio/"):
           if (self.multipass == False) or (self.passcounter == int(0)):
               self.audioconverter = gst.element_factory_make("audioconvert")
               self.pipeline.add(self.audioconverter)

               self.audioencoder = gst.element_factory_make(self.AudioEncoderPlugin)
               self.pipeline.add(self.audioencoder)
               if self.preset != "nopreset":
                   self.provide_presets()
                   GstPresetType = gobject.type_from_name("GstPreset")
                   if GstPresetType in gobject.type_interfaces(self.audioencoder):
                       for x in self.apreset:
                           self.audioencoder.load_preset(x)

                   self.audioresampler = gst.element_factory_make("audioresample")
                   self.pipeline.add(self.audioresampler)

                   self.acaps = gst.Caps()
                   self.acaps.append_structure(gst.Structure("audio/x-raw-float"))
                   self.acaps.append_structure(gst.Structure("audio/x-raw-int"))
                   for acap in self.acaps:
                       acap["rate"] = self.samplerate
                       acap["channels"] = self.channels
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

                   self.colorspaceconvert3 = gst.element_factory_make("ffmpegcolorspace")
                   self.pipeline.add(self.colorspaceconvert3)

           self.vcapsfilter2 = gst.element_factory_make("capsfilter")
           caps2 = gst.caps_from_string(self.videocaps)
           self.vcapsfilter2.set_property("caps", caps2)
           self.pipeline.add(self.vcapsfilter2)

           self.videoencoder = gst.element_factory_make(self.VideoEncoderPlugin)
           self.pipeline.add(self.videoencoder)
           if self.preset != "nopreset":
               GstPresetType = gobject.type_from_name("GstPreset")
               if GstPresetType in gobject.type_interfaces(self.videoencoder):
                   for x in self.vpreset:
                       self.videoencoder.load_preset(x)
                   if self.multipass != False:
                       cachefile =  (str(glib.get_user_cache_dir())+"/"+self.cachefilename)
                   if (self.multipass != False) and (self.passcounter == int(1)) :
                       self.videoencoder.load_preset("Pass 1")
                       self.videoencoder.set_property("statsfile", cachefile)
                   elif (self.multipass != False) and (self.passcounter == int(0)):
                       self.videoencoder.load_preset("Pass 2")
                       self.videoencoder.set_property("statsfile", cachefile)

           if (self.multipass == False) or (self.passcounter == int(0)):
               self.gstvideoqueue = gst.element_factory_make("queue")
               self.pipeline.add(self.gstvideoqueue)

           sink_pad.link(self.colorspaceconverter.get_pad("sink"))
           if self.preset != "nopreset":
               self.colorspaceconverter.link(self.videorate)
               self.videorate.link(self.videoscaler)
               self.videoscaler.link(self.vcapsfilter)
               if self.blackborderflag == True:
                   self.vcapsfilter.link(self.colorspaceconvert3)
                   self.colorspaceconvert3.link(self.videoboxer)
                   self.videoboxer.link(self.colorspaceconvert2)
               else:
                   self.vcapsfilter.link(self.colorspaceconvert2)
               self.colorspaceconvert2.link(self.videoencoder)
           else:
               self.colorspaceconverter.link(self.videoencoder)
               
               
           self.videoencoder.link(self.vcapsfilter2)
           if (self.multipass == False) or (self.passcounter == int(0)):
               self.vcapsfilter2.link(self.gstvideoqueue)
           else:
               self.vcapsfilter2.link(self.multipassfakesink)
           self.colorspaceconverter.set_state(gst.STATE_PAUSED)
           if self.preset != "nopreset":
               self.videoscaler.set_state(gst.STATE_PAUSED)
               self.videorate.set_state(gst.STATE_PAUSED)
               self.vcapsfilter.set_state(gst.STATE_PAUSED)
               if (self.multipass != False) and (self.passcounter == int(1)):
                  self.multipassfakesink.set_state(gst.STATE_PAUSED)
               if self.blackborderflag == True:
                   self.colorspaceconvert3.set_state(gst.STATE_PAUSED)
                   self.videoboxer.set_state(gst.STATE_PAUSED)
               self.colorspaceconvert2.set_state(gst.STATE_PAUSED)
           self.vcapsfilter2.set_state(gst.STATE_PAUSED)
           self.videoencoder.set_state(gst.STATE_PAUSED)
           if self.multipass == False or (self.passcounter == int(0)):
               self.gstvideoqueue.set_state(gst.STATE_PAUSED)
               print "linking videoqueue to container muxer since self.multipass is " + str(self.multipass)
               self.gstvideoqueue.link(self.containermuxer)
       else:
           raise Exception("Got a non-A/V pad!")
           # print "Got a non-A/V pad!"

   def Pipeline (self, state):
       if state == ("playing"):
           self.pipeline.set_state(gst.STATE_PLAYING)
       elif state == ("null"):
           self.pipeline.set_state(gst.STATE_NULL)
