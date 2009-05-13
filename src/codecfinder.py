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

# THIS CODE CAN PROBABLY BE REDUCED A LOT IN SIZE SINCE ITS 3 BIG FUNCTIONS DOING ESSENTIALLY THE SAME,
# ESPECIALLY NOW THAT THE ONLY SPECIAL CASING REMAINING IS FFMUXERS AND WAVPACK


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
                        'aac' : "audio/mpeg,mpegversion=[4, 2]", 'ac3' : "audio/x-ac3", 'speex' : "audio/x-speex", 
                        'celt' : "audio/x-celt", 'alac' : "audio/x-alac", 'wma2' : "audio/x-wma,wmaversion=2", 
                        'theora' : "video/x-theora", 'dirac' : "video/x-dirac", 'h264' : "video/x-h264", 
                        'mpeg2' : "video/mpeg,mpegversion=2", 'mpeg4' : "video/mpeg,mpegversion=4",
                        'xvid' : "video/x-xvid", 'dnxhd' : "video/x-dnxhd", 'wmv2' : "video/x-wmv,wmvversion=2",
                        'dnxhd' : "video/x-dnxhd", 'divx5' : "video/x-divx,divxversion=5", 'divx4' : "video/x-divx,divxversion=4"}
#####
#This code checks for available muxers and return a unique caps string
#for each. It also creates a python dictionary mapping the caps strings 
#to concrete element names. 
#####

def get_muxer_element(containercaps): 
   """
   Check all muxers for their caps and create a dictionary mapping caps 
   to element names. Then return elementname
   """

   muxerchoice = {}
   blacklist = ['rate','systemstream','packetsize']
   flist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
   muxers = []
   features = []
   for fact in flist:
       # FIXME: the and not part of this line should be removed, but it has to stay in until Ranks have 
       # been set on most muxers in GStreamer. If removed now we get lots of failures due to ending up 
       # with broken muxers
       if list_compat(["Codec", "Muxer"], fact.get_klass().split('/')) and not fact.get_name().startswith('ffmux'):
           muxers.append(fact.get_name())
           features.append(fact)
   muxerfeature = dict(zip(muxers, features))
   for x in muxers:
       muxer=x
       factory = gst.registry_get_default().lookup_feature(str(x))
       sinkcaps = [x.get_caps() for x in factory.get_static_pad_templates() if x.direction == gst.PAD_SRC]
       for caps in sinkcaps:
           result = caps[0].get_name()
           for attr in caps[0].keys():
               if attr not in blacklist:
                   result += ","+attr+"="+str(caps[0][attr])
       if muxerchoice.has_key(result):
           mostrecent = gst.PluginFeature.get_rank(muxerfeature[muxer])
           original = gst.PluginFeature.get_rank(muxerfeature[muxerchoice[result]])
           if mostrecent >= original:
               muxerchoice[result] = muxer
       else:
           muxerchoice[result] = muxer

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
def get_audio_encoder_element(audioencodercaps):
   """
   Check all audio encoders for their caps and create a dictionary 
   mapping caps to element names, only using the highest ranked element
   for each unique caps value. The input of the function is the unique caps
   and it returns the elementname. If the caps to not exist in dictionary it
   will return False.
   """

   audiocoderchoice = {}
   # blacklist all caps information we do not need to create a unique identifier
   blacklist = ['rate','channels','bitrate','block_align','mode','subbands'
               ,'allocation','framed','bitpool','blocks','width']
   flist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
   encoders = []
   features = []
   for fact in flist:
       if list_compat(["Codec", "Encoder", "Audio"], fact.get_klass().split('/')):
           # excluding wavpackenc as the fact that it got two SRC pads mess up the logic of this code
           if fact.get_name() != 'wavpackenc':
               encoders.append(fact.get_name())
               features.append(fact)
   encoderfeature = dict(zip(encoders, features))
   for x in encoders:
           codec = x
           factory = gst.registry_get_default().lookup_feature(str(x))
           sinkcaps = [x.get_caps() for x in factory.get_static_pad_templates() if x.direction == gst.PAD_SRC]
           for caps in sinkcaps:
               result = caps[0].get_name();
               for attr in caps[0].keys():
                   if attr not in blacklist:
                       result += ","+attr+"="+str(caps[0][attr])
           if audiocoderchoice.has_key(result):
                   mostrecent = gst.PluginFeature.get_rank(encoderfeature[codec])
                   original = gst.PluginFeature.get_rank(encoderfeature[audiocoderchoice[result]])
                   if mostrecent >= original:
                       audiocoderchoice[result] = codec
           else:
                   audiocoderchoice[result] = codec

   # print audiocoderchoice
   if audiocoderchoice.has_key(audioencodercaps):
       elementname = audiocoderchoice[audioencodercaps]
   else:
       elementname = False
   return elementname

#######
# This code checks for available video encoders and return a unique caps
# string for each. It also creates a python dictionary mapping the caps 
# strings to concrete element names.
#######

def get_video_encoder_element(videoencodercaps):
   """
   Check all video encoders for their caps and create a dictionary 
   mapping caps to element names, only using the highest ranked element
   for each unique caps value. The input of the function is the unique caps
   and it returns the elementname. If the caps to not exist in dictionary it
   will return False.
   """

   videocoderchoice = {}
   # blacklist all caps information we do not need to create a unique identifier
   blacklist = ['height','width','framerate','systemstream','depth']
   flist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
   encoders = []
   features = []
   for fact in flist:
       # print "fact is " + str(fact)
       if list_compat(["Codec", "Encoder", "Video"], fact.get_klass().split('/')):
           encoders.append(fact.get_name())
           features.append(fact) 
       elif list_compat(["Codec", "Encoder", "Image"], fact.get_klass().split('/')):
           encoders.append(fact.get_name())
           features.append(fact)
   encoderfeature = dict(zip(encoders, features))
   # print encoderfeature
   for x in encoders:
           element = x
           # print "encoder is " + str(codec)
           factory = gst.registry_get_default().lookup_feature(str(x))
           sinkcaps = [x.get_caps() for x in factory.get_static_pad_templates() if x.direction == gst.PAD_SRC]
           for caps in sinkcaps:
               # print "caps is "+ str(caps)
               result = caps[0].get_name();
               for attr in caps[0].keys():
                   if attr not in blacklist:
                       result += ","+attr+"="+str(caps[0][attr])
               # print "result is " + str(result)
               # print "videocodechoice before if statement"
               # print videocoderchoice
           if videocoderchoice.has_key(result):
                   mostrecent = gst.PluginFeature.get_rank(encoderfeature[element])
                   # print "fact is " + str(value)
                   # print str(codec) + " has rank " + str(mostrecent)
                   original = gst.PluginFeature.get_rank(encoderfeature[videocoderchoice[result]])
                   # print str(videocoderchoice[result]) + " has rank " + str(original)
                   # print "original value " + videocoderchoice[result]
                   if mostrecent >= original:
                       videocoderchoice[result] = element
                       # print "new value " + videocoderchoice[result]

           else:
                   videocoderchoice[result] = element
                   # print videocoderchoice
           videocoderchoice["video/x-divx,divxversion=5"] = "ffenc_mpeg4"
   # print videocoderchoice
   if videocoderchoice.has_key(videoencodercaps):
       elementname = videocoderchoice[videoencodercaps]
   else:
       elementname = False
   return elementname

