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
       containercaps = codecfinder.containermap[CONTAINERCHOICE]
       self.ContainerFormatPlugin = codecfinder.get_muxer_element(containercaps)

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
           # print "audiopasstoggle is false, setting AudioEncoderPlugin"
           # print "self.audiocaps IS **** " + str(self.audiocaps)
           self.AudioEncoderPlugin = codecfinder.get_audio_encoder_element(self.audiocaps)
       if self.videopasstoggle == False:
           # print "self.videopasstoggle is false so setting self.VideoEncoderPlugin"
           # print "look at incoming videocaps " + str(self.videocaps)
           self.VideoEncoderPlugin = codecfinder.get_video_encoder_element(self.videocaps)
           # print "self.VideoEncoderPlugin " + str(self.VideoEncoderPlugin)
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

       self.gstmultiqueue = gst.element_factory_make("multiqueue")
       self.multiqueueaudiosinkpad = self.gstmultiqueue.get_request_pad("sink0")
       self.multiqueuevideosinkpad = self.gstmultiqueue.get_request_pad("sink1")
       self.multiqueueaudiosrcpad = self.gstmultiqueue.get_pad("src0")
       self.multiqueuevideosrcpad = self.gstmultiqueue.get_pad("src1")

       self.pipeline.add(self.gstmultiqueue) 

       # print "audiopass toggle is " + str(self.audiopasstoggle)
       # print "videopass toggle is " + str(self.videopasstoggle)
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

       self.containermuxer = gst.element_factory_make(self.ContainerFormatPlugin, "containermuxer")
       videointersect = ("EMPTY")
       audiointersect = ("EMPTY")   
       factory = gst.registry_get_default().lookup_feature(self.ContainerFormatPlugin)
       for x in factory.get_static_pad_templates():
           if (x.direction == gst.PAD_SINK):
               sourcecaps = x.get_caps()
               if videointersect == ("EMPTY"): 
                   videointersect = sourcecaps.intersect(gst.caps_from_string(self.videocaps))
                   if videointersect != ("EMPTY"):
                   # print "pad is X which is " + str(x)
                       self.containermuxervideosinkpad = self.containermuxer.get_request_pad(x.name_template)
               if audiointersect == ("EMPTY"):
                   audiointersect = sourcecaps.intersect(gst.caps_from_string(self.audiocaps))
                   if audiointersect != ("EMPTY"):
                       self.containermuxeraudiosinkpad = self.containermuxer.get_request_pad(x.name_template)
       self.pipeline.add(self.containermuxer)

       # Add a tag setting Transmageddon as the application used for creating file if supported by format
       GstTagSetterType = gobject.type_from_name("GstTagSetter")
       if GstTagSetterType in gobject.type_interfaces(self.containermuxer):
           taglist=gst.TagList()
           taglist[gst.TAG_APPLICATION_NAME] = "Transmageddon"
           self.containermuxer.merge_tags(taglist, gst.TAG_MERGE_APPEND)

       self.transcodefileoutput = gst.element_factory_make("filesink", "transcodefileoutput")
       self.transcodefileoutput.set_property("location", (DESTDIR+"/"+self.outputfilename))
       self.pipeline.add(self.transcodefileoutput)

       self.containermuxer.link(self.transcodefileoutput)
       # print "reached end of first pipeline bulk, next step dynamic audio/video pads"
   

       self.uridecoder.set_state(gst.STATE_PAUSED)
       # print "setting uridcodebin to paused"
       self.BusMessages = self.BusWatcher()

       self.uridecoder.connect("no-more-pads", self.noMorePads) # we need to wait on this one before going further
       # print "connecting to no-more-pads"

       # Some encoders like x264enc are not able to handle odd height or widths
      # if width % 2:
        #   width += 1
      # if height % 2:
       #    height += 1

       if self.rotationvalue == 1 or self.rotationvalue == 3:
           # print "switching height and with around"
           nwidth = height
           nheight = width
           height = nheight
           width = nwidth

       # print "final height " + str(height) + " final width " + str(width)
     #  return height, width, num, denom, pixelaspectratio

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

   def list_compat(self, a1, b1):
       for x1 in a1:
           if not x1 in b1:
               return False
       return True

   def OnDynamicPad(self, dbin, sink_pad):
       c = sink_pad.get_caps().to_string()
       if c.startswith("audio/"):
           if self.stoptoggle==True:
               bus = self.pipeline.get_bus()
               bus.post(gst.message_new_application(self.pipeline, gst.Structure('STOP TRANSCODER')))
               return
           # First check for passthough mode
           if self.audiopasstoggle is False:
               # Check if either we are not doing multipass or if its the final pass before enabling audio
               if (self.multipass == False) or (self.passcounter == int(0)):
                   self.audioconverter = gst.element_factory_make("audioconvert")
                   self.pipeline.add(self.audioconverter)
                   self.audioencoder = gst.element_factory_make(self.AudioEncoderPlugin)
                   self.pipeline.add(self.audioencoder)
           
                   self.audioresampler = gst.element_factory_make("audioresample")
                   self.pipeline.add(self.audioresampler)
                   sink_pad.link(self.audioconverter.get_pad("sink"))

                   self.audioconverter.link(self.audioresampler)
                   self.audioresampler.link(self.audioencoder)

                   self.audioencoder.get_static_pad("src").link(self.multiqueueaudiosinkpad)
                   self.audioconverter.set_state(gst.STATE_PAUSED)
                   self.audioresampler.set_state(gst.STATE_PAUSED)
                   self.audioencoder.set_state(gst.STATE_PAUSED)
                   self.gstmultiqueue.set_state(gst.STATE_PAUSED)
                   self.multiqueueaudiosrcpad.link(self.containermuxeraudiosinkpad)

           else:
               # This code is for handling passthrough mode. 
               # TODO: dynamically plug correct parser. Iterate on parsers and intersect.
               # No parser if output is framed
               parsedcaps = gst.caps_from_string(self.audiocaps+",parsed=true")
               framedcaps = gst.caps_from_string(self.audiocaps+",framed=true")
               if (sink_pad.get_caps().is_subset(parsedcaps)) or (sink_pad.get_caps().is_subset(framedcaps)):
                   sink_pad.link(self.multiqueueaudiosinkpad)
                   self.multiqueueaudiosrcpad.link(self.containermuxeraudiosinkpad)
                   self.gstmultiqueue.set_state(gst.STATE_PAUSED)
               else:
                   flist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
                   parsers = []
                   self.aparserelement = False
                   for fact in flist:
                       # print "fact is " + str(fact)
                       if self.list_compat(["Codec", "Parser","Audio"], fact.get_klass().split('/')):
                           parsers.append(fact.get_name())
                           for x in parsers:
                               parser = x
                               factory = gst.registry_get_default().lookup_feature(str(x))
                               sinkcaps = [x.get_caps() for x in factory.get_static_pad_templates() if x.direction == gst.PAD_SRC]
                               parseintersect = ("EMPTY")   
                               for caps in sinkcaps:
                                   if parseintersect == ("EMPTY"):
                                       parseintersect = caps.intersect(gst.caps_from_string(self.audiocaps))
                                   if parseintersect != ("EMPTY"):
                                       self.aparserelement = parser
                   if self.aparserelement == False:
                                   error_message="noaudioparser"
                                   self.emit("got-error", error_message)
                                   self.stoptoggle=True
                                   return  
                   self.audioparse = gst.element_factory_make(self.aparserelement)
                   self.pipeline.add(self.audioparse)

                   # print "audiopad " + str(self.multiqueueaudiosinkpad)
                   sink_pad.link(self.audioparse.get_static_pad("sink"))
                   self.audioparse.get_static_pad("src").link(self.multiqueueaudiosinkpad)                    
                   self.multiqueueaudiosrcpad.link(self.containermuxeraudiosinkpad)
                   self.audioparse.set_state(gst.STATE_PAUSED)
                   self.gstmultiqueue.set_state(gst.STATE_PAUSED)

       elif c.startswith("video/"):
           if self.stoptoggle==True:
               bus = self.pipeline.get_bus()
               bus.post(gst.message_new_application(self.pipeline, gst.Structure('STOP TRANSCODER')))
               return
           if self.videopasstoggle == False:
               # print "Got an video cap"
               self.colorspaceconverter = gst.element_factory_make("ffmpegcolorspace")
               self.pipeline.add(self.colorspaceconverter)
               # checking for deinterlacer
               if self.interlaced == True:
                   self.deinterlacer = gst.element_factory_make("deinterlace", "deinterlacer")
                   self.pipeline.add(self.deinterlacer)
               self.videoflipper = gst.element_factory_make("videoflip")
               self.videoflipper.set_property("method", self.rotationvalue)
               self.pipeline.add(self.videoflipper)

               self.vcaps2 = gst.Caps()
               self.vcaps2 = gst.caps_from_string(self.videocaps)
               if self.preset != "nopreset":
                   height, width, num, denom, pixelaspectratio = self.provide_presets()
                   for vcap in self.vcaps2:
                       if pixelaspectratio != gst.Fraction(0, 0):
                           vcap["pixel-aspect-ratio"] = pixelaspectratio
               self.vcapsfilter2 = gst.element_factory_make("capsfilter")
               self.vcapsfilter2.set_property("caps", self.vcaps2)
               self.pipeline.add(self.vcapsfilter2)

 
               self.videoencoder = gst.element_factory_make(self.VideoEncoderPlugin)
               self.pipeline.add(self.videoencoder)

               # check if interlaced
               if self.interlaced:
                   sink_pad.link(self.deinterlacer.get_pad("sink"))
                   self.deinterlacer.link(self.videoflipper)
                   self.videoflipper.link(self.colorspaceconverter)
                   self.colorspaceconverter.link(self.videoencoder)
               else:
                   sink_pad.link(self.colorspaceconverter.get_pad("sink"))
                   self.colorspaceconverter.link(self.videoflipper)
                   self.videoflipper.link(self.videoencoder)

               self.videoencoder.link(self.vcapsfilter2)
               self.vcapsfilter2.get_static_pad("src").link(self.multiqueuevideosinkpad)

               self.colorspaceconverter.set_state(gst.STATE_PAUSED)
               if self.interlaced:
                   self.deinterlacer.set_state(gst.STATE_PAUSED)
               self.videoflipper.set_state(gst.STATE_PAUSED)  

               self.vcapsfilter2.set_state(gst.STATE_PAUSED)
               self.videoencoder.set_state(gst.STATE_PAUSED)
               self.gstmultiqueue.set_state(gst.STATE_PAUSED)
               self.multiqueuevideosrcpad.link(self.containermuxervideosinkpad)
           else:
               # Code for passthrough mode
               vparsedcaps = gst.caps_from_string(self.videocaps+",parsed=true")
               vframedcaps = gst.caps_from_string(self.videocaps+",framed=true")
               if (sink_pad.get_caps().is_subset(vparsedcaps)) or (sink_pad.get_caps().is_subset(vframedcaps)):
                   sink_pad.link(self.multiqueuevideosinkpad)
                   self.multiqueuevideosrcpad.link(self.containermuxervideosinkpad)
                   self.gstmultiqueue.set_state(gst.STATE_PAUSED)
               else:
                   flist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
                   parsers = []
                   self.vparserelement = False
                   for fact in flist:
                       if self.list_compat(["Codec", "Parser","Video"], fact.get_klass().split('/')):
                           parsers.append(fact.get_name())
                       elif self.list_compat(["Codec", "Parser"], fact.get_klass().split('/')):
                           parsers.append(fact.get_name())
                           for x in parsers:
                               parser = x
                               factory = gst.registry_get_default().lookup_feature(str(x))
                               sinkcaps = [x.get_caps() for x in factory.get_static_pad_templates() if x.direction == gst.PAD_SRC]
                               parseintersect = ("EMPTY")   
                               for caps in sinkcaps:
                                   if parseintersect == ("EMPTY"):
                                       parseintersect = caps.intersect(gst.caps_from_string(self.videocaps))
                                   if parseintersect != ("EMPTY"):
                                       self.vparserelement = parser                               
                   if self.vparserelement == False:
                                   error_message="novideoparser"
                                   self.emit("got-error", error_message)
                                   self.stoptoggle=True
                                   return


                   self.videoparse = gst.element_factory_make(self.vparserelement)
                   self.pipeline.add(self.videoparse)
                   sink_pad.link(self.videoparse.get_static_pad("sink"))
                   self.videoparse.get_static_pad("src").link(self.multiqueuevideosinkpad)
                   self.videoparse.set_state(gst.STATE_PAUSED)                    
                   self.multiqueuevideosrcpad.link(self.containermuxervideosinkpad)
                   self.gstmultiqueue.set_state(gst.STATE_PAUSED)
       else:
           raise Exception("Got a non-A/V pad!")
           # print "Got a non-A/V pad!"

   def Pipeline (self, state):
       if state == ("playing"):
           self.pipeline.set_state(gst.STATE_PLAYING)
       elif state == ("null"):
           self.pipeline.set_state(gst.STATE_NULL)
