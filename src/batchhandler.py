# Transmageddon
# Copyright (C) 2014 Christian Schaller <uraeus@gnome.org>
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
# License along with this library; if not, see <http://www.gnu.org/licenses/>.

# THIS CODE CAN PROBABLY BE REDUCED A LOT IN SIZE SINCE ITS 3 BIG FUNCTIONS
# DOING ESSENTIALLY THE SAME, ESPECIALLY NOW THAT THE ONLY SPECIAL CASING
# REMAINING IS FFMUXERS AND WAVPACK

from gi.repository import GLib
from gi.repository import Gst

def add_batch_job(streamdata, videodata, audiodata):
   keyfile = GLib.KeyFile.new()
   # Stream Data
   keyfile.set_string("streamdata 1", "filechoice", streamdata['filechoice'])
   keyfile.set_string("streamdata 1", "outputdirectory", streamdata['outputdirectory'])
   keyfile.set_string("streamdata 1", "filename", streamdata['filename'])
   keyfile.set_string("streamdata 1", "container", streamdata['container'].to_string())
   keyfile.set_string("streamdata 1", "devicename", streamdata['devicename'])
   keyfile.set_integer("streamdata 1", "multipass", streamdata['multipass'])
   keyfile.set_integer("streamdata 1", "passcounter", streamdata['passcounter'])
   keyfile.set_string("streamdata 1", "outputfilename", streamdata['outputfilename'])
   keyfile.set_string("streamdata 1", "timestamp", streamdata['timestamp'])
   if streamdata['dvdtitle'] != False:
      keyfile.set_string("streamdata 1", "dvdtitle", streamdata['dvdtitle'])
      keyfile.set_integer("streamdata 1", "singlestreamno", streamdata['singlestreamno'])

   # video data
   keyfile.set_integer("videodata 1", "videowidth", videodata[0]['videowidth'])
   keyfile.set_integer("videodata 1", "videoheight", videodata[0]['videoheight'])
   keyfile.set_string("videodata 1", "inputvideocaps", videodata[0]['inputvideocaps'].to_string())
   keyfile.set_string("videodata 1", "String", videodata[0]['outputvideocaps'].to_string())
   keyfile.set_integer("videodata 1", "videonum", videodata[0]['videonum'])
   keyfile.set_integer("videodata 1", "videodenom", videodata[0]['videodenom'])
   keyfile.set_string("videodata 1", "streamid", videodata[0]['streamid'])
   keyfile.set_boolean("videodata 1", "canpassthrough", videodata[0]['canpassthrough'])
   keyfile.set_boolean("videodata 1", "dopassthrough", videodata[0]['dopassthrough'])
   keyfile.set_boolean("videodata 1", "interlaced", videodata[0]['interlaced'])
   if videodata[0]['rotationvalue'] != False:
       keyfile.set_string("videodata 1", "rotationvalue", videodata[0]['rotationvalue'])

   # audio data
   keyfile.set_integer("audiodata 1", "audiochannels", audiodata[0]['audiochannels'])
   keyfile.set_integer("audiodata 1", "samplerate", audiodata[0]['samplerate'])
   keyfile.set_string("audiodata 1", "inputaudiocaps", audiodata[0]['inputaudiocaps'].to_string())
   keyfile.set_string("audiodata 1", "outputaudiocaps", audiodata[0]['outputaudiocaps'].to_string())
   keyfile.set_string("audiodata 1", "streamid", audiodata[0]['streamid'])
   keyfile.set_boolean("audiodata 1", "canpassthrough", audiodata[0]['canpassthrough'])
   keyfile.set_boolean("audiodata 1", "dopassthrough", audiodata[0]['dopassthrough'])
   keyfile.set_string("audiodata 1", "language", audiodata[0]['language'])
   keyfile.set_string("audiodata 1", "languagecode", audiodata[0]['languagecode'])

   keyfile.save_to_file("/tmp/transmageddon.keyfile")

def delete_batch_job():
    keyfile.remove_group ("streamdata 1")

def load_batch_job():
   print("loading")


