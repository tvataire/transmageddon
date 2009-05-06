#!/usr/bin/python

# Transmageddon
# Copyright (C) 2009 Christian Schaller <uraeus@gnome.org>
# Copyright (C) 2009 Edward Hervey <edward.hervey@collabora.co.uk>
# 
# Some code in this file came originally from the encode.py file in Pitivi
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

import pygst
pygst.require("0.10")
import gst

def list_compat(a1, b1):
   for x1 in a1:
       if not x1 in b1:
           return False
   return True

containermap = { 'Ogg' : "application/ogg",'Matroska' : "video/x-matroska", 'MXF' : "application/mxf", 'AVI' : "video/x-msvideo", 
                        'Quicktime' : "video/quicktime,variant=apple", 'MPEG4' : "video/quicktime,variant=iso", 'MPEG PS' : "ffmux_mpeg", 
                        'MPEG TS' : "video/mpegts", 'FLV' : "video/x-flv", '3GPP' : "video/quicktime,variant=3gpp" }

csuffixmap =   { 'Ogg' : ".ogg", 'Matroska' : ".mkv", 'MXF' : ".mxf", 'AVI' : ".avi", 'Quicktime' : ".mov",
                        'MPEG4' : ".mp4", 'MPEG PS' : ".mpg", 'MPEG TS' : ".ts", 'FLV' : ".flv", '3GPP' : ".3gp" }

codecmap = {     'vorbis' : "audio/x-vorbis", 'flac' : "audio/x-flac", 'mp3' : "audio/mpeg,mpegversion=1,layer=3", 
                        'aac' : "audio/mpeg,mpegversion=4", 'ac3' : "audio/x-ac3", 'speex' : "audio/x-speex", 
                        'celt' : "audio/x-celt", 'alac' : "audio/x-alac", 'wma2' : "audio/x-wma,wmaversion=2", 
                        'theora' : "video/x-theora", 'dirac' : "video/x-dirac", 'h264' : "video/x-h264", 
                        'mpeg2' : "video/mpeg,mpegversion=2", 'mpeg4' : "video/mpeg,mpegversion=4",
                        'xvid' : "video/x-xvid", 'dnxhd' : "video/x-dnxhd", 'wmv2' : "video/x-wmv,wmvversion=2",
                        'dnxhd' : "video/x-dnxhd" }
#####
#This code checks for available muxers and return a unique caps string
#for each. It also creates a python dictionary mapping the caps strings 
#to concrete element names. 
#####

def available_muxers():
   """ return all available muxers except the broken ffmpeg ones """
   flist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
   res = []
   for fact in flist:
       if list_compat(["Codec", "Muxer"], fact.get_klass().split('/')) and not fact.get_name().startswith('ffmux'):
           res.append(fact.get_name())
   return res

def get_muxer_element(containercaps): 
   """
   Check all muxers for their caps and create a dictionary mapping caps 
   to element names. Then return elementname
   """
   muxers = available_muxers()
   stringcaps = []
   blacklist = ['rate','systemstream','packetsize']
   for x in muxers:
       factory = gst.registry_get_default().lookup_feature(str(x))
       sinkcaps = [x.get_caps() for x in factory.get_static_pad_templates() if x.direction == gst.PAD_SRC]
       for caps in sinkcaps:
           result = caps[0].get_name();
           for attr in caps[0].keys():
               if attr not in blacklist:
                   result += ","+attr+"="+str(caps[0][attr])
           stringcaps.append(result)

   # print stringcaps
   muxerchoice = dict(zip(stringcaps, muxers))
   if muxerchoice.has_key(containercaps):
       elementname = muxerchoice[containercaps]
   else:
       elementname = False
   return elementname

######
#   This code checks for available audio encoders and return a unique caps string for each.
#   It also creates a python dictionary mapping the caps strings to concrete element
#   names.
#####
def available_audio_encoders():
   """ returns all available audio encoders """
   flist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
   res = []
   for fact in flist:
       if list_compat(["Codec", "Encoder", "Audio"], fact.get_klass().split('/')):
           # excluding wavpackenc as the fact that it got two SRC pads mess up the logic of this code
           if fact.get_name() != 'wavpackenc':
               res.append(fact.get_name())
           else:
               print ""
   return res

def get_audio_encoder_element(audioencodercaps):
   """
   Check all audio encoders for their caps and create a dictionary 
   mapping caps to element names. Then return elementname.
   """
   audioencoders = available_audio_encoders()
   audiocaps = []
   # blacklist all caps information we do not need to create a unique identifier
   blacklist = ['rate','channels','bitrate','block_align','mode','subbands'
               ,'allocation','framed','bitpool','blocks','width']
   for x in audioencoders:
       factory = gst.registry_get_default().lookup_feature(str(x))
       sinkcaps = [x.get_caps() for x in factory.get_static_pad_templates() if x.direction == gst.PAD_SRC]
       for caps in sinkcaps:
           result = caps[0].get_name();
           for attr in caps[0].keys():
               if attr not in blacklist:
                   result += ","+attr+"="+str(caps[0][attr])
           audiocaps.append(result)
   # print audiocaps 
   audioencoderchoice = dict(zip(audiocaps, audioencoders))
   if audioencoderchoice.has_key(audioencodercaps):
       elementname = audioencoderchoice[audioencodercaps]
   else:
       elementname = False
   return elementname

#######
# This code checks for available video encoders and return a unique caps
# string for each. It also creates a python dictionary mapping the caps 
# strings to concrete element names.
#######

def available_video_encoders():
   """ returns all available video encoders """
   flist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
   res = []
   for fact in flist:
       if list_compat(["Codec", "Encoder", "Video"], fact.get_klass().split('/')):
           if fact.get_name() != 'ffenc_libtheora':
               res.append(fact.get_name())
           elif 'theoraenc' in res:
               print "adding nothing"
           else:
               res.append(fact.get_name()) 
       elif list_compat(["Codec", "Encoder", "Image"], fact.get_klass().split('/')):
           res.append(fact.get_name())
   return res 

def get_video_encoder_element(videoencodercaps):
   """
   Check all video encoders for their caps and create a dictionary 
   mapping caps to element names. Then return elementname.
   """
   encoders = available_video_encoders()
   videocaps = []
   # blacklist all caps information we do not need to create a unique identifier
   blacklist = ['height','width','framerate','systemstream','depth']
   for x in encoders:
       factory = gst.registry_get_default().lookup_feature(str(x))
       sinkcaps = [x.get_caps() for x in factory.get_static_pad_templates() if x.direction == gst.PAD_SRC]
       for caps in sinkcaps:
           result = caps[0].get_name();
           for attr in caps[0].keys():
               if attr not in blacklist:
                   result += ","+attr+"="+str(caps[0][attr])
           videocaps.append(result)
   # print videocaps
   videoencoderchoice = dict(zip(videocaps, encoders))
   # print videoencoderchoice
   if videoencoderchoice.has_key(videoencodercaps):
       elementname = videoencoderchoice[videoencodercaps]
   else:
       elementname = False
   return elementname

