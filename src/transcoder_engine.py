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

   def __init__(self, FILECHOSEN, FILENAME, DESTDIR, CONTAINERCHOICE, AUDIOCODECVALUE, VIDEOCODECVALUE, PRESET, 
                      OHEIGHT, OWIDTH, FRATENUM, FRATEDEN, ACHANNELS, MULTIPASS, PASSCOUNTER, OUTPUTNAME, 
                      TIMESTAMP, ROTATIONVALUE, AUDIOPASSTOGGLE, VIDEOPASSTOGGLE):
       gobject.GObject.__init__(self)

       # Choose plugin based on Container name
       containercaps = codecfinder.containermap[CONTAINERCHOICE]
       self.ContainerFormatPlugin = codecfinder.get_muxer_element(containercaps)

       # Choose plugin based on Codec Name
       # or switch to remuxing mode if any of the values are set to 'pastr'

       self.audiocaps = AUDIOCODECVALUE
       self.videocaps = VIDEOCODECVALUE
       self.audiopasstoggle = AUDIOPASSTOGGLE
       # print "audiopass toggle is " + str(self.audiopasstoggle)
       self.videopasstoggle = VIDEOPASSTOGGLE
       
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
       # print "self.multiqueueaudiosinkpad " + str(self.multiqueueaudiosinkpad)
       self.multiqueuevideosinkpad = self.gstmultiqueue.get_request_pad("sink1")
       # print "self.multiqueuevideosinkpad " + str(self.multiqueuevideosinkpad)
       self.multiqueueaudiosrcpad = self.gstmultiqueue.get_pad("src0")
       # print "self.multiqueueaudiosrcpad " + str(self.multiqueueaudiosrcpad)
       self.multiqueuevideosrcpad = self.gstmultiqueue.get_pad("src1")
       # print "self.multiqueuevideosrcpad " + str(self.multiqueuevideosrcpad)
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
       
       if (self.multipass == False) or (self.passcounter == int(0)):
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


           self.transcodefileoutput = gst.element_factory_make("filesink", "transcodefileoutput")
           self.transcodefileoutput.set_property("location", (DESTDIR+"/"+self.outputfilename))
           self.pipeline.add(self.transcodefileoutput)

           self.containermuxer.link(self.transcodefileoutput)
           # print "reached end of first pipeline bulk, next step dynamic audio/video pads"
       else:
           self.multipassfakesink = gst.element_factory_make("fakesink", "multipassfakesink")
           self.pipeline.add(self.multipassfakesink)    

       self.uridecoder.set_state(gst.STATE_PAUSED)
       # print "setting uridcodebin to paused"
       self.BusMessages = self.BusWatcher()

       self.uridecoder.connect("no-more-pads", self.noMorePads) # we need to wait on this one before going further
       # print "connecting to no-more-pads"
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
       # print "owidth is " + str(self.owidth) + " oheight is " + str(self.oheight)
       self.vpreset = []       
       voutput = preset.vcodec.presets[0].split(", ")
       for x in voutput:
           self.vpreset.append(x)
       self.apreset = []
       aoutput = preset.acodec.presets[0].split(", ")
       for x in aoutput:
           self.apreset.append(x)
         
       # Get Display aspect ratio
       pixelaspectratio = preset.vcodec.aspectratio[0]

       # Scale width / height down
       if self.owidth > wmax:
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
               # print "adding width borders"
               px = (wmin - width) / 2
               self.vbox['left'] = -px
               self.vbox['right'] = -px
               self.vbox['top'] = -0
               self.vbox['bottom'] = -0
           elif height < hmin:
               # print " adding height borders"
               px = (hmin - height) / 2
               self.vbox['top'] = -px
               self.vbox['bottom'] = -px
               self.vbox['left'] = -int(0)
               self.vbox['right'] = -int(0)
           else:
               self.vbox['top'] = -int(0)
               self.vbox['bottom'] = -int(0)
               self.vbox['left'] = -int(0)
               self.vbox['right'] = -int(0)

       # Setup video framerate and add to caps - 
       # FIXME: Is minimum framerate really worthwhile checking for?
       # =================================================================
       rmin = preset.vcodec.rate[0].num / float(preset.vcodec.rate[0].denom)
       rmax = preset.vcodec.rate[1].num / float(preset.vcodec.rate[1].denom)
       rmaxtest = preset.vcodec.rate[1]
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

       if self.rotationvalue == 1 or self.rotationvalue == 3:
           # print "switching height and with around"
           nwidth = height
           nheight = width
           height = nheight
           width = nwidth

       # print "final height " + str(height) + " final width " + str(width)
       return height, width, num, denom, pixelaspectratio

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
           gst.DEBUG_BIN_TO_DOT_FILE (self.pipeline, gst.DEBUG_GRAPH_SHOW_ALL, 'transmageddon.dot')
       elif mtype == gst.MESSAGE_ASYNC_DONE:
           self.emit('ready-for-querying')
       elif mtype == gst.MESSAGE_EOS:
           if (self.multipass != False):
               if (self.passcounter == 0):
                   #removing multipass cache file when done
                   os.remove(self.cachefile)
           self.emit('got-eos')
           self.pipeline.set_state(gst.STATE_NULL)
       return True

   def list_compat(self, a1, b1):
       for x1 in a1:
           if not x1 in b1:
               return False
       return True

   def OnDynamicPad(self, dbin, sink_pad):
       c = sink_pad.get_caps().to_string()
       if c.startswith("audio/"):
           # print "audio pad found"
           if self.audiopasstoggle == False:
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
                   #for acap in self.acaps:
                   #    acap["rate"] = self.samplerate
                   #    acap["channels"] = self.channels
                   self.acapsfilter = gst.element_factory_make("capsfilter")
                   self.acapsfilter.set_property("caps", self.acaps)
                   self.pipeline.add(self.acapsfilter)

               sink_pad.link(self.audioconverter.get_pad("sink"))

               if self.preset != "nopreset":
                   self.audioconverter.link(self.audioresampler)
                   self.audioresampler.link(self.acapsfilter)
                   self.acapsfilter.link(self.audioencoder)
               else:
                   self.audioconverter.link(self.audioencoder)
               self.audioencoder.get_static_pad("src").link(self.multiqueueaudiosinkpad)
               self.audioconverter.set_state(gst.STATE_PAUSED)
               if self.preset != "nopreset":
                   self.audioresampler.set_state(gst.STATE_PAUSED)
                   self.acapsfilter.set_state(gst.STATE_PAUSED)
               self.audioencoder.set_state(gst.STATE_PAUSED)
               self.gstmultiqueue.set_state(gst.STATE_PAUSED)
               self.multiqueueaudiosrcpad.link(self.containermuxeraudiosinkpad)


           else:
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
                                       print "parser " + str(parser)
                   # TODO: Need to handle the case when no parser is found
            
                   self.audioparse = gst.element_factory_make(self.aparserelement)
                   self.pipeline.add(self.audioparse)

                   # print "audiopad " + str(self.multiqueueaudiosinkpad)
                   sink_pad.link(self.audioparse.get_static_pad("sink"))
                   self.audioparse.get_static_pad("src").link(self.multiqueueaudiosinkpad)                    
                   self.multiqueueaudiosrcpad.link(self.containermuxeraudiosinkpad)
                   self.audioparse.set_state(gst.STATE_PAUSED)
                   self.gstmultiqueue.set_state(gst.STATE_PAUSED)

       elif c.startswith("video/"):
           if self.videopasstoggle == False:
               # print "Got an video cap"
               self.colorspaceconverter = gst.element_factory_make("ffmpegcolorspace")
               self.pipeline.add(self.colorspaceconverter)

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

               if self.preset != "nopreset":
                   self.colorspaceconvert2 = gst.element_factory_make("ffmpegcolorspace")
                   self.pipeline.add(self.colorspaceconvert2)
           
                   self.vcaps = gst.Caps()
                   self.vcaps.append_structure(gst.Structure("video/x-raw-rgb"))
                   self.vcaps.append_structure(gst.Structure("video/x-raw-yuv"))
                   height, width, num, denom, pixelaspectratio = self.provide_presets()
                   for vcap in self.vcaps:
                       vcap["width"] = width
                       vcap["height"] = height
                       vcap["framerate"] = gst.Fraction(num, denom)
                       if pixelaspectratio != gst.Fraction(0, 0):
                           vcap["pixel-aspect-ratio"] = pixelaspectratio                   

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
               self.videoencoder = gst.element_factory_make(self.VideoEncoderPlugin)
               self.pipeline.add(self.videoencoder)
               if self.preset != "nopreset":
                   GstPresetType = gobject.type_from_name("GstPreset")
                   if GstPresetType in gobject.type_interfaces(self.videoencoder):
                       for x in self.vpreset:
                           self.videoencoder.load_preset(x)
                       if (self.multipass != False) and (self.passcounter != int(0)) :
                           passvalue = "Pass "+ str(self.passcounter)
                           bob = self.videoencoder.load_preset(passvalue)
                           self.videoencoder.set_property("multipass-cache-file", self.cachefile)
                       elif (self.multipass != False) and (self.passcounter == int(0)):
                           self.videoencoder.load_preset("Pass " + str(self.multipass))
                           self.videoencoder.set_property("multipass-cache-file", self.cachefile)
             
               # needs to be moved to before multiqueu ? if (self.multipass == False) or (self.passcounter == int(0)):
               sink_pad.link(self.colorspaceconverter.get_pad("sink"))
               if self.preset != "nopreset":
                   self.colorspaceconverter.link(self.videoflipper)
                   self.videoflipper.link(self.videorate)
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
                   self.colorspaceconverter.link(self.videoflipper)
                   self.videoflipper.link(self.videoencoder)
               self.videoencoder.link(self.vcapsfilter2)
               if (self.multipass == False) or (self.passcounter == int(0)):
                   self.vcapsfilter2.get_static_pad("src").link(self.multiqueuevideosinkpad)
               else:
                   self.vcapsfilter2.link(self.multipassfakesink)
               self.colorspaceconverter.set_state(gst.STATE_PAUSED)
               self.videoflipper.set_state(gst.STATE_PAUSED)  
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
                   self.gstmultiqueue.set_state(gst.STATE_PAUSED)
                   self.multiqueuevideosrcpad.link(self.containermuxervideosinkpad)
           else:
               vparsedcaps = gst.caps_from_string(self.videocaps+",parsed=true")
               vframedcaps = gst.caps_from_string(self.videocaps+",framed=true")
               if (sink_pad.get_caps().is_subset(vparsedcaps)) or (sink_pad.get_caps().is_subset(vframedcaps)):
                   sink_pad.link(self.multiqueuevideosinkpad)
                   self.multiqueuevideosrcpad.link(self.containermuxervideosinkpad)
                   self.gstmultiqueue.set_state(gst.STATE_PAUSED)
               else:
                   flist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
                   parsers = []
                   for fact in flist:
                       if self.list_compat(["Codec", "Parser","Video"], fact.get_klass().split('/')):
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
