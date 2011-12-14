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
from gi.repository import Gst
Gst.init(None)
from gi.repository import GstPbutils

class Transcoder(GObject.GObject):

   __gsignals__ = {
            'ready-for-querying' : (GObject.SignalFlags.RUN_LAST, None, []),
            'got-eos' : (GObject.SignalFlags.RUN_LAST, None, []),
            'got-error' : (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))
                    }

   def __init__(self, FILECHOSEN, FILENAME, DESTDIR, CONTAINERCHOICE, AUDIOCODECVALUE, VIDEOCODECVALUE, PRESET, 
                      OHEIGHT, OWIDTH, FRATENUM, FRATEDEN, ACHANNELS, MULTIPASS, PASSCOUNTER, OUTPUTNAME, 
                      TIMESTAMP, ROTATIONVALUE, AUDIOPASSTOGGLE, VIDEOPASSTOGGLE, INTERLACED, INPUTVIDEOCAPS):
       GObject.GObject.__init__(self)

       # Choose plugin based on Container name
       self.container = CONTAINERCHOICE
       self.audiocaps = AUDIOCODECVALUE
       if self.container != False:
           self.containercaps = Gst.caps_from_string(codecfinder.containermap[CONTAINERCHOICE])
       # special case mp3 which is a no-container format with a container (id3mux)
       else:
           if self.audiocaps.intersect(Gst.caps_from_string("audio/mpeg, mpegversion=1, layer=3")):
               self.containercaps=Gst.caps_from_string("application/x-id3")
               self.container=Gst.caps_from_string("application/x-id3")


       # Choose plugin based on Codec Name
       # or switch to remuxing mode if any of the values are set to 'pastr'
       self.stoptoggle=False
       self.videocaps = VIDEOCODECVALUE # "novid" means we have a video file input, but do not want it
                                        #  while False means we don't have any video
       self.audiopasstoggle = AUDIOPASSTOGGLE
       self.interlaced = INTERLACED
       self.videopasstoggle = VIDEOPASSTOGGLE
       self.inputvideocaps = INPUTVIDEOCAPS
       self.doaudio= False
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

       # switching width and height around for rotationchoices where it makes sense
       if self.rotationvalue == 1 or self.rotationvalue == 3:
           nwidth = self.oheight
           nheight = self.owidth
           self.oheight = nheight
           self.owidth = nwidth 

       # if needed create a variable to store the filename of the multipass \
       # statistics file
       if self.multipass != False:
           self.cachefile = (str (glib.get_user_cache_dir()) + "/" + \
                   "multipass-cache-file" + self.timestamp + ".log")

       # gather preset data if relevant
       if self.preset != "nopreset":
           height, width, num, denom, pixelaspectratio = self.provide_presets()
           for acap in self.audiocaps:
               acap["channels"] = self.channels
           for vcap in self.videocaps:
               vcap["height"] = int(height)
               vcap["width"] = int(width)
               vcap["framerate"] = Gst.Fraction(num, denom)
               if pixelaspectratio != Gst.Fraction(0, 0):
                   vcap["pixel-aspect-ratio"] = pixelaspectratio


       # Create transcoding pipeline
       self.pipeline = Gst.Pipeline()
       self.pipeline.set_state(Gst.State.PAUSED)

       self.uridecoder = Gst.ElementFactory.make("uridecodebin", "uridecoder")
       print "self.uridecoder " + str(self.uridecoder)
       print "FILECHOSEN " + str(FILECHOSEN)
       self.uridecoder.set_property("uri", FILECHOSEN)
       self.uridecoder.connect("pad-added", self.OnDynamicPad)
       self.uridecoder.set_state(Gst.State.PAUSED)

       # first check if we have a container format, if not set up output for possible outputs
       #  should not be hardcoded

       audiopreset=None
       videopreset=None
       if self.preset != "nopreset": 
           # print "got preset and will use Quality Normal"
           # these values should not be hardcoded, but gotten from profile XML file
           audiopreset="Quality Normal"
           videopreset="Quality Normal"

       if self.container==False:
           if self.audiocaps.intersect(Gst.caps_from_string("audio/mpeg, mpegversion=4")):
               self.audiocaps=Gst.caps_from_string("audio/mpeg, mpegversion=4, stream-format=adts")
           elif self.audiocaps.intersect(Gst.caps_from_string("audio/x-flac")):
               self.audiocaps=Gst.caps_from_string("audio/x-flac")
       else:
           print "self.containercaps is " +str(self.containercaps)
           # the "Null" here must be a binding bug
           self.encodebinprofile = GstPbutils.EncodingContainerProfile.new("containerformat", "Null" , self.containercaps, "Normal")
       if self.audiocaps != False:
           if self.container==False:
               self.encodebinprofile = GstPbutils.EncodingAudioProfile.new (self.audiocaps, audiopreset, Gst.Caps.new_any(), 0)
           else:
               print "here we are"
               print "self.audiocaps is " + str(self.audiocaps)
               print "audiopreset is " +str(audiopreset)
               audiopreset="Normal"
               self.audioprofile = GstPbutils.EncodingAudioProfile.new(self.audiocaps, audiopreset, Gst.Caps.new_any(), 0)
               self.encodebinprofile.add_profile(self.audioprofile)
       if self.videocaps != "novid":
           if (self.videocaps != False):
               videopreset="Normal"
               self.videoprofile = GstPbutils.EncodingVideoProfile.new(self.videocaps, videopreset, Gst.Caps.new_any(), 0)
               self.encodebinprofile.add_profile(self.videoprofile)
       self.encodebin = Gst.ElementFactory.make ("encodebin", None)
       self.encodebin.set_property("profile", self.encodebinprofile)
       self.encodebin.set_property("avoid-reencoding", True)
       self.pipeline.add(self.encodebin)
       self.encodebin.set_state(Gst.State.PAUSED)

       if self.videopasstoggle==False:
           if self.container != False:
               self.videoflipper = Gst.ElementFactory.make('videoflip', None)
               self.videoflipper.set_property("method", self.rotationvalue)
               self.pipeline.add(self.videoflipper)

               #self.deinterlacer = Gst.ElementFactory.make('deinterlace', None)
               #self.pipeline.add(self.deinterlacer)

               self.colorspaceconversion = Gst.ElementFactory.make('videoconvert', None)
               self.pipeline.add(self.colorspaceconversion)
                       
               #self.deinterlacer.link(self.colorspaceconversion)
	       self.colorspaceconversion.link(self.videoflipper)
               #self.deinterlacer.set_state(Gst.State.PAUSED)
               self.colorspaceconversion.set_state(Gst.State.PAUSED)
               self.videoflipper.set_state(Gst.State.PAUSED)

       self.remuxcaps = Gst.Caps()
       if self.audiopasstoggle:
          self.remuxcaps.append(self.audiocaps)
       if self.videopasstoggle:
          self.remuxcaps.append(self.videocaps)
       if self.audiopasstoggle and not self.videopasstoggle:
          self.remuxcaps.append_structure(Gst.Structure("video/x-raw-rgb"))
          self.remuxcaps.append_structure(Gst.Structure("video/x-raw-yuv"))
       if self.videopasstoggle and not self.audiopasstoggle:
          self.remuxcaps.append_structure(Gst.Structure("audio/x-raw-float"))
          self.remuxcaps.append_structure(Gst.Structure("audio/x-raw-int"))
       if self.videocaps=="novid":
          if self.inputvideocaps != None:
              self.remuxcaps.append(self.inputvideocaps)
              self.remuxcaps.append_structure(Gst.Structure("audio/x-raw-float"))
              self.remuxcaps.append_structure(Gst.Structure("audio/x-raw-int"))


       if (self.audiopasstoggle) or (self.videopasstoggle) or (self.videocaps=="novid"):
           self.uridecoder.set_property("caps", self.remuxcaps)

 
       self.pipeline.add(self.uridecoder)

       self.transcodefileoutput = Gst.ElementFactory.make("filesink", \
               "transcodefileoutput")
       self.transcodefileoutput.set_property("location", \
               (DESTDIR+"/"+self.outputfilename))
       self.pipeline.add(self.transcodefileoutput)
       self.encodebin.link(self.transcodefileoutput)

       self.uridecoder.set_state(Gst.State.PAUSED)

       # print "setting uridcodebin to paused"
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
       # set audio and video caps from preset file
       self.audiocaps=Gst.caps_from_string(preset.acodec.name)
       self.videocaps=Gst.caps_from_string(preset.vcodec.name)
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

       # print "final height " + str(height) + " final width " + str(width)
       return height, width, num, denom, pixelaspectratio

   def noMorePads(self, dbin):
       if (self.multipass == False) or (self.passcounter == int(0)):
           self.transcodefileoutput.set_state(Gst.State.PAUSED)
       glib.idle_add(self.idlePlay)
       # print "No More pads received"

   def idlePlay(self):
        self.Pipeline("playing")
        # print "gone to playing"
        return False

   def BusWatcher(self):
     bus = self.pipeline.get_bus()
     bus.add_signal_watch()
     bus.connect('message', self.on_message)

   def on_message(self, bus, message):
       mtype = message.type
       # print mtype
       if mtype == Gst.MessageType.ERROR:
           print "we got an error, life is shit"
           err, debug = message.parse_error()
           print err 
           print debug
           #Gst.DEBUG_BIN_TO_DOT_FILE (self.pipeline, Gst.DEBUG_GRAPH_SHOW_ALL, \
           #        'transmageddon.dot')
           #self.emit('got-error', err.message)
       elif mtype == Gst.MessageType.ASYNC_DONE:
           self.emit('ready-for-querying')
       elif mtype == Gst.MessageType.EOS:
           if (self.multipass != False):
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
       print "src_pad is" +str(src_pad)
       origin = src_pad.query_caps()
       if (self.container==False):
           a =  origin.to_string()
           if a.startswith("audio/"):
               sinkpad = self.encodebin.get_static_pad("audio_0")
               src_pad.link(sinkpad)
       else:
           if self.videocaps == "novid":
               c = origin.to_string()
               if c.startswith("audio/"):
                   sinkpad = self.encodebin.emit("request-pad", origin)
                   d = sinkpad.query_caps().to_string()
                   if d.startswith("audio/"):
                       src_pad.link(sinkpad)
           else:
               # Checking if its a subtitle pad which we can't deal with
               # currently.0
               # Making sure that when we remove video from a file we don't
               # bother with the video pad.
               c = origin.to_string()
               if not c.startswith("text/"):
                   if not (c.startswith("video/") and (self.videocaps == False)):
                       # print "creating sinkpad"
                       sinkpad = self.encodebin.emit("request-pad", origin)
               if c.startswith("audio/"):
                   src_pad.link(sinkpad)
               elif ((c.startswith("video/") or c.startswith("image/")) and (self.videocaps != False)):
                   if self.videopasstoggle==False:
                       # port fix- should be self.deinterlacer
                       src_pad.link(self.colorspaceconversion.get_static_pad("sink"))
                       self.videoflipper.get_static_pad("src").link(sinkpad)
                       
                   else:
                       srccaps=src_pad.get_caps()
                       srcstring=srccaps.to_string()
                       #print "source pad is " + str(srcstring)
                       sinkcaps=sinkpad.get_caps()
                       sinkstring=sinkcaps.to_string()
                       #print "sinkpad is " + str(sinkstring)
                       src_pad.link(sinkpad)

       # Grab element from encodebin which supports tagsetter interface and set app name
       # to Transmageddon
       GstTagSetterType = GObject.type_from_name("GstTagSetter")
       tag_setting_element=self.encodebin.get_by_interface(GstTagSetterType)
       if tag_setting_element != None:
           taglist=Gst.TagList()
           taglist[Gst.TAG_ENCODER] = "Transmageddon encoder" # this should probably be set to
	                                                      # string combining audio+video encoder
                                                              # implementations
           taglist[Gst.TAG_APPLICATION_NAME] = "Transmageddon transcoder"
           tag_setting_element.merge_tags(taglist, Gst.TAG_MERGE_APPEND)

   def Pipeline (self, state):
       if state == ("playing"):
           self.pipeline.set_state(Gst.State.PLAYING)
       elif state == ("null"):
           self.pipeline.set_state(Gst.State.NULL)
