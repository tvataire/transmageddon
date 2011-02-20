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

   def __init__(self, FILECHOSEN, FILENAME, DESTDIR, CONTAINERCHOICE, AUDIOCODECVALUE, ACHANNELS, 
                      OUTPUTNAME, TIMESTAMP, AUDIOPASSTOGGLE):
       gobject.GObject.__init__(self)

       # Choose plugin based on Container name
       print "Containerchoice is " + str(CONTAINERCHOICE)
       if CONTAINERCHOICE != "No container":
           containercaps = codecfinder.containermap[CONTAINERCHOICE]
           print "containercaps is " + str(containercaps)
           self.ContainerFormatPlugin = codecfinder.get_muxer_element(containercaps)

       # Choose plugin based on Codec Name
       # or switch to remuxing mode if any of the values are set to 'pastr'
       self.stoptoggle=False
       self.audiocaps = AUDIOCODECVALUE
       self.audiopasstoggle = AUDIOPASSTOGGLE
       self.doaudio= False
       if self.audiopasstoggle == False:
           self.AudioEncoderPlugin = codecfinder.get_audio_encoder_element(self.audiocaps)
       self.achannels = ACHANNELS
       self.outputfilename = OUTPUTNAME
       self.timestamp = TIMESTAMP
       self.vbox = {}
       self.containerchoice = CONTAINERCHOICE
       # Create transcoding pipeline
       self.pipeline = gst.Pipeline("TranscodingPipeline")
       self.pipeline.set_state(gst.STATE_PAUSED)

       self.uridecoder = gst.element_factory_make("uridecodebin", "uridecoder")
       self.uridecoder.set_property("uri", FILECHOSEN)
       self.uridecoder.connect("pad-added", self.OnDynamicPad)

       self.gstmultiqueue = gst.element_factory_make("multiqueue")
       self.multiqueueaudiosinkpad = self.gstmultiqueue.get_request_pad("sink0")
       self.multiqueueaudiosrcpad = self.gstmultiqueue.get_pad("src0")
       self.pipeline.add(self.gstmultiqueue) 

       self.remuxcaps = gst.Caps()
       if self.audiopasstoggle:
          self.remuxcaps.append(self.audiocaps)
       if not self.audiopasstoggle:
          self.remuxcaps.append_structure(gst.Structure("audio/x-raw-float"))
          self.remuxcaps.append_structure(gst.Structure("audio/x-raw-int"))  

       if (self.audiopasstoggle):

           self.uridecoder.set_property("caps", self.remuxcaps)
       self.pipeline.add(self.uridecoder)

       if self.containerchoice != "No container":
           print "self.containerformatplugin is " + str(self.ContainerFormatPlugin)
           self.containermuxer = gst.element_factory_make(self.ContainerFormatPlugin, "audiocontainermuxer")
           print " successful container muxer creation" + str(self.containermuxer)
           audiointersect = ("EMPTY")   
           factory = gst.registry_get_default().lookup_feature(self.ContainerFormatPlugin)
           for x in factory.get_static_pad_templates():
               if (x.direction == gst.PAD_SINK):
                   sourcecaps = x.get_caps()
                   if audiointersect == ("EMPTY"):
                       audiointersect = sourcecaps.intersect(gst.caps_from_string(self.audiocaps))
                       if audiointersect != ("EMPTY"):
                           self.containermuxeraudiosinkpad = self.containermuxer.get_request_pad(x.name_template)
           self.pipeline.add(self.containermuxer)
       #else:
       #    factory = gst.registry_get_default().lookup_feature(self.audioencoder)
       #    for x in factory.get_static_pad_templates():
       #        if (x.direction == gst.PAD_SINK):
       #            self.audioencodersinkpad = self.audioencoder.get_request_pad(x.name_template)

           # Add a tag setting Transmageddon as the application used for creating file if supported by format
	   GstTagSetterType = gobject.type_from_name("GstTagSetter")
	   if GstTagSetterType in gobject.type_interfaces(self.containermuxer):
	       taglist=gst.TagList()
	       taglist[gst.TAG_APPLICATION_NAME] = "Transmageddon"
               self.containermuxer.merge_tags(taglist, gst.TAG_MERGE_APPEND)

       self.transcodefileoutput = gst.element_factory_make("filesink", "transcodefileoutput")
       self.transcodefileoutput.set_property("location", (DESTDIR+"/"+self.outputfilename))
       self.pipeline.add(self.transcodefileoutput)

       self.uridecoder.set_state(gst.STATE_PAUSED)
       # print "setting uridcodebin to paused"
       self.BusMessages = self.BusWatcher()

       self.uridecoder.connect("no-more-pads", self.noMorePads) # we need to wait on this one before going further
       # print "connecting to no-more-pads

   def noMorePads(self, dbin):
       self.transcodefileoutput.set_state(gst.STATE_PAUSED)
       if self.containerchoice != "No container":
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
               self.audioconverter = gst.element_factory_make("audioconvert")
               self.pipeline.add(self.audioconverter)
               self.audioencoder = gst.element_factory_make(self.AudioEncoderPlugin)
               self.pipeline.add(self.audioencoder)
     
               self.audioresampler = gst.element_factory_make("audioresample")
               self.pipeline.add(self.audioresampler)
               sink_pad.link(self.audioconverter.get_pad("sink"))

               self.audioconverter.link(self.audioresampler)
               self.audioresampler.link(self.audioencoder)

               self.audioconverter.set_state(gst.STATE_PAUSED)
               self.audioresampler.set_state(gst.STATE_PAUSED)
               self.audioencoder.set_state(gst.STATE_PAUSED)
               self.gstmultiqueue.set_state(gst.STATE_PAUSED)
               if self.containerchoice != "No container":
                   self.audioencoder.get_static_pad("src").link(self.multiqueueaudiosinkpad)
                   self.multiqueueaudiosrcpad.link(self.containermuxeraudiosinkpad)
                   self.containermuxer.link(self.transcodefileoutput)
               else:
                    self.audioencoder.link(self.transcodefileoutput)
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
               if CONTAINERCHOICE != "None":                   
                   self.multiqueueaudiosrcpad.link(self.containermuxeraudiosinkpad)
                   self.containermuxer.link(self.transcodefileoutput)
               else:
                   self.multiqueueaudiosrcpad.link(self.transcodefileoutput)
               self.audioparse.set_state(gst.STATE_PAUSED)
               self.gstmultiqueue.set_state(gst.STATE_PAUSED)

   def Pipeline (self, state):
       if state == ("playing"):
           self.pipeline.set_state(gst.STATE_PLAYING)
       elif state == ("null"):
           self.pipeline.set_state(gst.STATE_NULL)
