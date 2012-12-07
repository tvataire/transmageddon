# Transmageddon
# Copyright (C) 2009-2011 Christian Schaller <uraeus@gnome.org>
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
from gi.repository import GObject
GObject.threads_init()
from gi.repository import GLib
from gi.repository import Gst
Gst.init(None)
from gi.repository import GstPbutils

class Transcoder(GObject.GObject):

   __gsignals__ = {
            'ready-for-querying' : (GObject.SignalFlags.RUN_LAST, None, []),
            'got-eos' : (GObject.SignalFlags.RUN_LAST, None, []),
            'missing-plugin' : (GObject.SignalFlags.RUN_LAST, None, []),
            'got-error' : (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))
                    }

   def __init__(self, FILECHOSEN, FILENAME, DESTDIR, CONTAINERCHOICE, AUDIODATA, VIDEODATA, PRESET, 
                      MULTIPASS, PASSCOUNTER, OUTPUTNAME, TIMESTAMP, ROTATIONVALUE):
       GObject.GObject.__init__(self)

       # Choose plugin based on Container name
       self.audiodata = AUDIODATA
       self.videodata = VIDEODATA
       self.container = CONTAINERCHOICE
       #self.audiocaps = self.audiodata[0]['outputaudiocaps']
       if self.container != False:
           self.containercaps = Gst.caps_from_string(codecfinder.containermap[CONTAINERCHOICE])
       # special case mp3 which is a no-container format with a container (id3mux)
       else:
           if self.audiocaps.intersect(Gst.caps_from_string("audio/mpeg, mpegversion=1, layer=3")):
               self.containercaps=Gst.caps_from_string("application/x-id3")
               self.container=Gst.caps_from_string("application/x-id3")

       # set preset directory
       Gst.preset_set_app_dir("/usr/share/transmageddon/presets/")

       # Choose plugin based on Codec Name
       # or switch to remuxing mode if any of the values are set to 'pastr'
       self.stoptoggle=False
       #self.videocaps = self.videodata[0]['outputvideocaps']  # "novid" means we have a video file input, but do not want it
       #self.audiopasstoggle = AUDIOPASSTOGGLE
       #self.interlaced = INTERLACED
       #self.videopasstoggle = VIDEOPASSTOGGLE
       #self.inputvideocaps = INPUTVIDEOCAPS
       self.doaudio= False
       self.preset = PRESET
       #self.oheight = OHEIGHT
       #self.owidth = OWIDTH
       #self.fratenum = FRATENUM
       #self.frateden = FRATEDEN
       #self.achannels = self.audiodata[0]['audiochannels']
       #self.astreamid = self.audiodata[0]['streamid']
       self.blackborderflag = False
       self.multipass = MULTIPASS
       self.passcounter = PASSCOUNTER
       self.outputfilename = OUTPUTNAME
       self.timestamp = TIMESTAMP
       self.rotationvalue = int(ROTATIONVALUE)
       self.missingplugin= False
       self.probestreamid = False
       self.sinkpad = False
       print(self.sinkpad)

          

       # switching width and height around for rotationchoices where it makes sense
       if self.rotationvalue == 1 or self.rotationvalue == 3:
           nwidth = self.oheight
           nheight = self.owidth
           self.oheight = nheight
           self.owidth = nwidth 

       # if needed create a variable to store the filename of the multipass \
       # statistics file
       if self.multipass != 0:
           self.cachefile = (str (GLib.get_user_cache_dir()) + "/" + \
                   "multipass-cache-file" + self.timestamp + ".log")

       # gather preset data if relevant
       if self.preset != "nopreset":
           self.provide_presets()
 
       # Create transcoding pipeline
       self.pipeline = Gst.Pipeline()
       self.pipeline.set_state(Gst.State.PAUSED)

       # first check if we have a container format, if not set up output 
       # for possible outputs should not be hardcoded

       audiopreset=None
       videopreset=None
       if self.preset != "nopreset": 
           # print "got preset and will use Quality Normal"
           # these values should not be hardcoded, but gotten from profile XML file
           audiopreset=None
           videopreset=None

       # first check if we are using a container format
       if self.container==False:
           if self.audiocaps.intersect(Gst.caps_from_string("audio/mpeg, mpegversion=4")):
               self.audiocaps=Gst.caps_from_string("audio/mpeg, mpegversion=4, stream-format=adts")
           elif self.audiocaps.intersect(Gst.caps_from_string("audio/x-flac")):
               self.audiocaps=Gst.caps_from_string("audio/x-flac")
       else:
           self.encodebinprofile = GstPbutils.EncodingContainerProfile.new("containerformat", None , self.containercaps, None)
 
           # What to do if we are not doing video passthrough (we only support video inside a 
           # container format
           if self.videodata[0]['outputvideocaps'] !=False:
               if (self.videodata[0]['dopassthrough']==False and self.passcounter == int(0)):
                   self.videoflipper = Gst.ElementFactory.make('videoflip', None)
                   self.videoflipper.set_property("method", self.rotationvalue)
                   self.pipeline.add(self.videoflipper)

                   self.colorspaceconverter = Gst.ElementFactory.make("videoconvert", None)
                   self.pipeline.add(self.colorspaceconverter)

                   self.deinterlacer = Gst.ElementFactory.make('deinterlace', None)
                   self.pipeline.add(self.deinterlacer)
   
                   self.deinterlacer.link(self.colorspaceconverter)
                   self.colorspaceconverter.link(self.videoflipper)
                   self.deinterlacer.set_state(Gst.State.PAUSED)
                   self.colorspaceconverter.set_state(Gst.State.PAUSED)
                   self.videoflipper.set_state(Gst.State.PAUSED)
           # this part of the pipeline is used for both passthrough and re-encoding
           if self.videodata[0]['outputvideocaps'] != "novid":
               if (self.videodata[0]['outputvideocaps'] != False):
                   videopreset=None
                   self.videoprofile = GstPbutils.EncodingVideoProfile.new(self.videodata[0]['outputvideocaps'], videopreset, Gst.Caps.new_any(), 0)
                   self.encodebinprofile.add_profile(self.videoprofile)

       # We do not need to do anything special for passthrough for audio, since we are not
       # including any extra elements between uridecodebin and encodebin
       if self.audiodata[0]['outputaudiocaps'] != False:
           print("We should add only one audio pad to encodebin")
           if self.container==False:
               print("yo")
               print(self.audiodata[0]['outputaudiocaps'])
               self.encodebinprofile = GstPbutils.EncodingAudioProfile.new (self.audiodata[0]['outputaudiocaps'], audiopreset, Gst.Caps.new_any(), 0)
           else:
               print("yay")
               audiopreset=None
               self.audioprofile = GstPbutils.EncodingAudioProfile.new(self.audiodata[0]['outputaudiocaps'], audiopreset, Gst.Caps.new_any(), 0)
               self.encodebinprofile.add_profile(self.audioprofile)
       
       if self.passcounter != int(0):
           passvalue = "Pass "+ str(self.passcounter)
           videoencoderplugin = codecfinder.get_video_encoder_element(self.videodata[0]['outputvideocaps'])
           self.videoencoder = Gst.ElementFactory.make(videoencoderplugin,"videoencoder")
           self.pipeline.add(self.videoencoder)
           GstPresetType = GObject.type_from_name("GstPreset")
           if GstPresetType in GObject.type_interfaces(self.videoencoder):
               bob = self.videoencoder.load_preset(passvalue)
               self.videoencoder.set_property("multipass-cache-file", self.cachefile)
           self.multipassfakesink = Gst.ElementFactory.make("fakesink", "multipassfakesink")
           self.pipeline.add(self.multipassfakesink)
           self.videoencoder.set_state(Gst.State.PAUSED)
           self.multipassfakesink.set_state(Gst.State.PAUSED)


       else:
           self.encodebin = Gst.ElementFactory.make ("encodebin", None)
           self.encodebin.connect("element-added", self.OnEncodebinElementAdd)
           self.encodebin.set_property("profile", self.encodebinprofile)
           self.encodebin.set_property("avoid-reencoding", True)
           self.pipeline.add(self.encodebin)
           self.encodebin.set_state(Gst.State.PAUSED)
       
       # put together remuxing caps to set on uridecodebin if doing 
       # passthrough on audio or video

       if self.audiodata[0]['dopassthrough'] or self.videodata[0]['dopassthrough']:
           self.remuxcaps = Gst.Caps.new_empty()
       if self.audiodata[0]['dopassthrough']:
          self.remuxcaps.append(self.audiodata[0]['inputaudiocaps'])
       if self.videodata[0]['dopassthrough']:
          self.remuxcaps.append(self.videodata[0]['inputvideocaps'])
       if self.audiodata[0]['dopassthrough'] and not self.videodata[0]['dopassthrough']:
          videostruct=Gst.Structure.from_string("video/x-raw")
          self.remuxcaps.append_structure(videostruct[0])
       if self.videodata[0]['dopassthrough'] and not self.audiodata[0]['dopassthrough']:
          audiostruct=Gst.Structure.from_string("audio/x-raw")
          self.remuxcaps.append_structure(audiostruct[0])
       if self.videodata[0]['outputvideocaps']=="novid":
          if self.videodata[0]['inputvideocaps'] != None:
              self.remuxcaps.append(self.videodata[0]['inputvideocaps'])
              audiostruct=Gst.Structure.from_string("audio/x-raw")
              self.remuxcaps.append_structure(audiostruct[0])

       self.uridecoder = Gst.ElementFactory.make("uridecodebin", "uridecoder")
       self.uridecoder.set_property("uri", FILECHOSEN)
       self.uridecoder.connect("pad-added", self.OnDynamicPad)

       if (self.audiodata[0]['dopassthrough']) or (self.videodata[0]['dopassthrough']) or (self.videodata[0]['outputvideocaps']=="novid"):
           self.uridecoder.set_property("caps", self.remuxcaps) 
       self.uridecoder.set_state(Gst.State.PAUSED)
       self.pipeline.add(self.uridecoder)
       
       if self.passcounter != int(0):
           self.videoencoder.link(self.multipassfakesink)
       else:
           self.transcodefileoutput = Gst.ElementFactory.make("filesink", \
               "transcodefileoutput")
           self.transcodefileoutput.set_property("location", \
               (DESTDIR+"/"+self.outputfilename))
           self.pipeline.add(self.transcodefileoutput)
           self.encodebin.link(self.transcodefileoutput)
           self.transcodefileoutput.set_state(Gst.State.PAUSED)
       self.uridecoder.set_state(Gst.State.PAUSED)

       self.BusMessages = self.BusWatcher()

       # we need to wait on this one before going further
       self.uridecoder.connect("no-more-pads", self.noMorePads)
       # print "connecting to no-more-pads"

   # Get all preset values
   def reverse_lookup(self,v):
       for k in codecfinder.codecmap:
           if codecfinder.codecmap[k] == v:
               return k

   # Gather preset values and create preset elements
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

       # Get Display aspect ratio
       pixelaspectratio = preset.vcodec.aspectratio

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
           width=wmax
           height=hmax

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

       # set audio and video caps from preset file
       self.audiocaps=Gst.caps_from_string(preset.acodec.name+","+"channels="+str(self.channels))
       self.videocaps=Gst.caps_from_string(preset.vcodec.name+","+"height="+str(height)+","+"width="+str(width)+","+"framerate="+str(num)+"/"+str(denom))
       # self.videocaps.set_value("pixelaspectratio", pixelaspectratio) this doesn't work due to pixelaspectratio being a fraction, 
       # needs further investigation


       # print "final height " + str(height) + " final width " + str(width)
       # return height, width, num, denom, pixelaspectratio

   def noMorePads(self, dbin):
       if self.passcounter == int(0):
           self.transcodefileoutput.set_state(Gst.State.PAUSED)
       GLib.idle_add(self.idlePlay)
       # print "No More pads received"

   def idlePlay(self):
        self.Pipeline("playing")
        # print "gone to playing"
        return False

   def BusWatcher(self):
     bus = self.pipeline.get_bus()
     bus.add_signal_watch()
     bus.connect('message', self.on_message)

   def padprobe(self, pad, probeinfo, userdata):
       event = probeinfo.get_event()
       eventtype=event.type
       if eventtype==Gst.EventType.STREAM_START:
           self.probestreamid = event.parse_stream_start()
           if self.probestreamid==self.audiodata[0]['streamid']:
               pad.link(self.sinkpad)
       return Gst.PadProbeReturn.OK

   def on_message(self, bus, message):
       mtype = message.type
       # print(mtype)
       if mtype == Gst.MessageType.ERROR:
           print("we got an error, life is shit")
           err, debug = message.parse_error()
           print(err) 
           print(debug)
           Gst.debug_bin_to_dot_file (self.pipeline, \
           Gst.DebugGraphDetails.ALL, 'transmageddon-debug-graph')
           #self.emit('got-error', err.message)
       elif mtype == Gst.MessageType.ELEMENT:
           if GstPbutils.is_missing_plugin_message(message):
               if self.missingplugin==False: #don't think this is correct if more than one plugin installed
                   self.missingplugin=message
                   #output=GstPbutils.missing_plugin_message_get_description(message)
                   #print(output)
                   # GstPbutils.missing_plugin_message_get_installer_detail(message)
                   self.emit('missing-plugin')
           
       elif mtype == Gst.MessageType.ASYNC_DONE:
           self.emit('ready-for-querying')
       elif mtype == Gst.MessageType.EOS:
           if (self.multipass != 0):
               if (self.passcounter == 0):
                   #removing multipass cache file when done
                   if os.access(self.cachefile, os.F_OK):
                       os.remove(self.cachefile)
           self.emit('got-eos')
           self.pipeline.set_state(Gst.State.NULL)
       elif mtype == Gst.MessageType.APPLICATION:
           self.pipeline.set_state(Gst.State.NULL)
           self.pipeline.remove(self.uridecoder)
       return True

   def OnDynamicPad(self, uridecodebin, src_pad):
       origin = src_pad.query_caps(None)
       if (self.container==False):
           a =  origin.to_string()
           if a.startswith("audio/"):
               sinkpad = self.encodebin.get_static_pad("audio_0")
               src_pad.link(sinkpad)
       else:
           if self.videodata[0]['outputvideocaps'] == "novid":
               c = origin.to_string()
               if c.startswith("audio/"):
                   sinkpad = self.encodebin.emit("request-pad", origin)
                   d = sinkpad.query_caps(None).to_string()
                   if d.startswith("audio/"):
                       src_pad.link(sinkpad)
           else:
               # Checking if its a subtitle pad which we can't deal with
               # currently.
               # Making sure that when we remove video from a file we don't
               # bother with the video pad.
               print("we are where we want to be")
               c = origin.to_string()
               if not c.startswith("text/"):
                   if not (c.startswith("video/") and (self.videodata[0]['outputvideocaps'] == False)):
                       if self.passcounter == int(0):
                           self.sinkpad = self.encodebin.emit("request-pad", origin)
               if c.startswith("audio/"):
                   print("ok, now we are getting somewhere")
                   if self.passcounter == int(0):
                       # self.sinkpad = self.encodebin.emit("request-pad", origin)
                       src_pad.add_probe(Gst.PadProbeType.EVENT_DOWNSTREAM, self.padprobe, None)
                       #if self.probestreamid==self.astreamid:
                       #    print("got streamid from probe")
                       #    src_pad.link(sinkpad)
               elif ((c.startswith("video/") or c.startswith("image/")) and (self.videodata[0]['outputvideocaps'] != False)):
                   print("video detected")
                   if self.videodata[0]['dopassthrough']==False:
                       if (self.multipass != 0) and (self.passcounter != int(0)):
                           videoencoderpad = self.videoencoder.get_static_pad("sink")
                           src_pad.link(videoencoderpad)
                       else:
                           # src_pad.add_probe(Gst.PadProbeType.EVENT_DOWNSTREAM, self.padprobe, None)
                           deinterlacerpad = self.deinterlacer.get_static_pad("sink")
                           src_pad.link(deinterlacerpad)
                           self.videoflipper.get_static_pad("src").link(self.sinkpad)   
                   else:
                           src_pad.link(self.sinkpad)

   def OnEncodebinElementAdd(self, encodebin, element):
       factory=element.get_factory()
       name=element.get_name()
       if factory != None:
           # set multipass cache file on video encoder element
           if (self.multipass != 0) and (self.passcounter == int(0)):
               if Gst.ElementFactory.list_is_type(factory, 2814749767106562): # this is the factory code for Video encoders
                   element.set_property("multipass-cache-file", self.cachefile)
           
           # Set Transmageddon as Application name using Tagsetter interface
           tagyes = factory.has_interface("GstTagSetter")
           #print(str(name) + " got GstTagSetter Interface " +str(tagyes))
           if tagyes ==True:
               taglist=Gst.TagList.new_empty()
               # Gst.TagList.add_value(taglist, Gst.TagMergeMode.APPEND, Gst.TAG_APPLICATION_NAME, "Transmageddon transcoder" tag_setting_element.merge_tags(taglist, Gst.TAG_MERGE_APPEND)

   def Pipeline (self, state):
       if state == ("playing"):
           self.pipeline.set_state(Gst.State.PLAYING)
       elif state == ("null"):
           self.pipeline.set_state(Gst.State.NULL)
