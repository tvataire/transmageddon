"""
    Arista Presets
    ==============
    Objects for handling devices, presets, etc. 
    
    Example Use
    -----------
    Presets are automatically loaded when the module is initialized.
    
        >>> import transmageddon.presets
        >>> transmageddon.presets.get()
        { "name": Device, ... }
    
    If you have other paths to load, use:
    
        >>> transmageddon.presets.load("file")
        >>> transmageddon.presets.load_directory("path")
    
    License
    -------
    Copyright 2008 - 2009 Daniel G. Taylor <dan@programmer-art.org>
    
    This file is part of Arista.

    Arista is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as 
    published by the Free Software Foundation, either version 2.1 of
    the License, or (at your option) any later version.

    Foobar is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public
    License along with Arista.  If not, see
    <http://www.gnu.org/licenses/>.
"""

# import gettext
import logging
import os
import sys
import urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree
import gstfraction

from gi.repository import Gst

import utils

# _ = gettext.gettext
_presets = {}
_log = logging.getLogger("transmageddon.presets")

UPDATE_LOCATION = "http://programmer-art.org" + \
                  "/media/releases/transmageddon-transcoder/presets/"

class Fraction(gstfraction.Fraction):
    """
        An object for storing a fraction as two integers. This is a subclass
        of gst.Fraction that allows initialization from a string representation
        like "1/2".
    """
    def __init__(self, value = "1"):
        """
            @type value: str
            @param value: Either a single number or two numbers separated by
                          a '/' that represent a fraction
        """
        parts = value.split("/")

        if len(parts) == 1:
            gstfraction.Fraction.__init__(self, int(value))
        elif len(parts) == 2:
            gstfraction.Fraction.__init__(self, int(parts[0]))
        else:
            raise ValueError("Not a valid integer or fraction: %(value)s!") % {
                "value": value,
            }

class Author(object):
    """
        An author object that stores a name and an email.
    """
    def __init__(self, name = "", email = ""):
        """
            @type name: str
            @param name: The author's full name
            @type email: str
            @param email: The email address of the author
        """
        self.name = name
        self.email = email
    
    def __repr__(self):
        return "%s <%s>" % (self.name, self.email)

class Device(object):
    """
        A device holds information about a product and several presets for that
        product. This includes the make, model, version, etc.
    """
    def __init__(self, make = "Generic", model = "", description = "", 
                 author = None, version = "", presets = None, icon = "", 
                 default = ""):
        """
            @type make: str
            @param make: The make of the product, e.g. Apple
            @type model: str
            @param model: The model of the product, e.g. iPod
            @type description: str
            @param description: A user-friendly description of these presets
            @type author: Author
            @param author: The author of these presets
            @type version: str
            @param version: The version of these presets (not the product)
            @type presets: dict
            @param presets: A dictionary of presets where the keys are the
                            preset names
            @type icon: str
            @param icon: A URI to an icon. Only file:// and stock:// are
                         allowed, where stock refers to a GTK stock icon
            @type default: str
            @param default: The default preset name to use (if blank then the
                            first available preset is used)
        """
        self.make = make
        self.model = model
        self.description = description
        
        if author is not None:
            self.author = author
        else:
            self.author = Author()
            
        self.version = version
        self.presets = presets and presets or {}
        self.icon = icon
        self.default = default
        
        self.filename = None
    
    def __repr__(self):
        return "%s %s" % (self.make, self.model)
    
    @property
    def name(self):
        """
            Get a friendly name for this device.
            
            @rtype: str
            @return: Either the make and model or just the model of the device
                     for generic devices
        """
        if self.make == "Generic":
            return self.model
        else:
            return "%s %s" % (self.make, self.model)

class Preset(object):
    """
        A preset representing audio and video encoding options for a particular
        device.
    """
    def __init__(self, name = "", container = "", extension = "", 
                 acodec = None, vcodec = None):
        """
            @type name: str
            @param name: The name of the preset, e.g. "High Quality"
            @type container: str
            @param container: The container element name, e.g. ffmux_mp4
            @type extension: str
            @param extension: The filename extension to use, e.g. mp4
            @type acodec: AudioCodec
            @param acodec: The audio encoding settings
            @type vcodec: VideoCodec
            @param vcodec: The video encoding settings
        """
        self.name = name
        self.container = container
        self.extension = extension
        self.acodec = acodec
        self.vcodec = vcodec
    
    def __repr__(self):
        return "%s %s" % (self.name, self.container)

class Codec(object):
    """
        Settings for encoding audio or video. This object defines options
        common to both audio and video encoding.
    """
    def __init__(self, name = "", container = ""):
        """
            @type name: str
            @param name: The name of the encoding GStreamer element, e.g. faac
            @type container: str
            @param container: A container to fall back to if only audio xor
                              video is present, e.g. for plain mp3 audio you
                              may not want to wrap it in an avi or mp4; if not
                              set it defaults to the preset container
        """
        self.name = name
        self.container = container
        self.rate = (Fraction(), Fraction())
        self.presets = []
    
    def __repr__(self):
        return "%s %s" % (self.name, self.container)

class AudioCodec(Codec):
    """
        Settings for encoding audio.
    """
    def __init__(self, *args):
        Codec.__init__(self, *args)
        self.sample = (96000)
        self.width = (8, 24)
        self.depth = (8, 24)
        self.channels = (1, 6)

class VideoCodec(Codec):
    """
        Settings for encoding video.
    """
    def __init__(self, *args):
        Codec.__init__(self, *args)
        self.border = "N"
        self.passes ="0"
        self.rate = (Fraction("1"), Fraction("60"))
        self.aspectratio = Fraction("1/1")
        self.width = (2, 1920)
        self.height = (2, 1080)

def _parse_range(value, type = int):
    """
        Parse a string into a range.
        
            >>> _parse_range("1")
            (1, 1)
            >>> _parse_range("2, 5")
            (2, 5)
            >>> _parse_range("1.0, 6", type = float)
            (1.0, 6.0)
        
        @type value: str
        @param value: A string value to be parsed
        @type type: type
        @param type: The type to coerce value into
    """
    parts = value.split(",")
    
    if len(parts) == 1:
        return (type(parts[0]), type(parts[0]))
    elif len(parts) == 2:
        return (type(parts[0]), type(parts[1]))
    else:
        raise ValueError(ngettext("Value may only contain one comma; got %(value)s") % {
            "value": value
        })

def _load_author(root):
    """
        Load an author from a given xml element.
        
        @type root: xml.etree.Element
        @param root: An author element with name and email children
        @rtype: Author
        @return: A new Author instance
    """
    author = Author()
    
    for child in root:
        if child.tag == "name":
            author.name = child.text.strip()
        elif child.tag == "email":
            author.email = child.text.strip()
    
    return author

def _load_audio_codec(root):
    """
        Load an audio codec from a given xml element.
        
        @type root: xml.etree.Element
        @param root: An audio codec element
        @rtype: AudioCodec
        @return: A new AudioCodec instance
    """
    codec = AudioCodec()
    
    for child in root:
        if child.tag == "name":
            codec.name = child.text.strip()
        elif child.tag == "container":
            codec.container = child.text.strip()
        elif child.tag == "width":
            codec.width = _parse_range(child.text.strip())
        elif child.tag == "depth":
            codec.depth = _parse_range(child.text.strip())
        elif child.tag == "channels":
            codec.channels = _parse_range(child.text.strip())
        elif child.tag == "samplerate":
            codec.samplerate = child.text.strip()
        elif child.tag == "presets":
            for command in child:
                codec.presets.append(command.text.strip())
    
    return codec

def _load_video_codec(root):
    """
        Load a video codec from a given xml element.
        
        @type root: xml.etree.Element
        @param root: An video codec element
        @rtype: VideoCodec
        @return: A new VideoCodec instance
    """
    codec = VideoCodec()
    
    for child in root:
        if child.tag == "name":
            codec.name = child.text.strip()
        elif child.tag == "container":
            codec.container = child.text.strip()
        elif child.tag == "width":
            codec.width = _parse_range(child.text.strip())
        elif child.tag == "height":
            codec.height = _parse_range(child.text.strip())
        elif child.tag == "pixelaspectratio":
            aspectratio = child.text.strip()
            if aspectratio != "0/0":
                codec.aspectratio = _parse_range(child.text.strip(), Fraction)
        elif child.tag == "framerate":
            codec.rate = _parse_range(child.text.strip(), Fraction)
        elif child.tag == "border":
            codec.border = child.text.strip()
        elif child.tag == "passes":
            codec.passes = child.text.strip()
        elif child.tag == "presets":
            for command in child:
                codec.presets.append(command.text.strip())
    
    return codec

def _load_preset(root):
    """
        Load a preset from a given xml element.
        
        @type root: xml.etree.Element
        @param root: An preset element
        @rtype: Preset
        @return: A new preset instance
    """
    preset = Preset()
    
    for child in root:
        if child.tag == "name":
            preset.name = child.text.strip()
        elif child.tag == "container":
            preset.container = child.text.strip()
        elif child.tag == "extension":
            preset.extension = child.text.strip()
        elif child.tag == "audio":
            preset.acodec = _load_audio_codec(child)
        elif child.tag == "video":
            preset.vcodec = _load_video_codec(child)

    if preset.acodec and not preset.acodec.container:
        preset.acodec.container = preset.container
    
    if preset.vcodec and not preset.vcodec.container:
        preset.vcodec.container = preset.container
        
    return preset

def load(filename):
    """
        Load a filename into a new Device.
        
        @type filename: str
        @param filename: The file to load
        @rtype: Device
        @return: A new device instance loaded from the file
    """
    tree = xml.etree.ElementTree.parse(filename)
    
    device = Device()
    
    device.filename = filename
    
    for child in tree.getroot():
        if child.tag == "make":
            device.make = child.text.strip()
        elif child.tag == "model":
            device.model = child.text.strip()
        elif child.tag == "description":
            device.description = child.text.strip()
        elif child.tag == "author":
            device.author = _load_author(child)
        elif child.tag == "version":
            device.version = child.text.strip()
        elif child.tag == "profile":
            profile = (_load_preset(child))
            device.presets[profile.name] = profile
        elif child.tag == "icon":
            device.icon = child.text.strip()
        elif child.tag == "default":
            device.default = child.text.strip()
    
    _log.debug(("Loaded device %(device)s (%(presets)d presets)") % {
        "device": device.name,
        "presets": len(device.presets)
    })
    
    return device

def load_directory(directory):
    """
        Load an entire directory of device presets.
        
        @type directory: str
        @param directory: The path to load
        @rtype: dict
        @return: A dictionary of all the loaded devices
    """
    global _presets
    for filename in os.listdir(directory):
        if filename.endswith("xml"):
            _presets[filename[:-4]] = load(os.path.join(directory, filename))
    return _presets

def get():
    """
        Get all loaded device presets.
        
        @rtype: dict
        @return: A dictionary of Device objects where the keys are the short
                 name for the device
    """
    return _presets

def version_info():
    """
        Generate a string of version information. Each line contains 
        "name, version" for a particular preset file, where name is the key
        found in transmageddon.presets.get().
        
        This is used for checking for updates.
    """
    info = ""
    
    for name, device in list(_presets.items()):
        info += "%s, %s\n" % (name, device.version)
        
    return info

def install_preset(location, name):
    """
        Attempt to fetch and install a preset. Presets are always installed
        to ~/.transmageddon/presets/.
        
        @type location: str
        @param location: The location of the preset
        @type name: str
        @param name: The name of the preset to fetch, without any extension
    """
    local_path = os.path.expanduser(os.path.join("~", ".transmageddon", "presets"))
    
    if not os.path.exists(local_path):
        os.makedirs(local_path)
    
    if not location.endswith("/"):
        location = location + "/"
    
    for ext in ["xml", "svg"]:
        path = ".".join([location + name, ext])
        _log.debug(("Fetching %(location)s") % {
            "location": path,
        })
        
        try:
            f = urllib.request.urlopen(path)
            local_file = os.path.join(local_path, ".".join([name, ext]))
            _log.debug(("Writing to %(file)s") % {
                "file": local_file,
            })
            open(local_file, "w").write(f.read())
        except Exception as e:
            _log.error(("There was an error fetching and installing " \
                         "%(location)s: %(error)s") % {
                "location": path,
                "error": str(e),
            })

def check_for_updates(location = UPDATE_LOCATION):
    """
        Check for updated presets from a central server.
        
        @type location: str
        @param location: The directory where presets.txt and all preset files
                         can be found on the server
        @rtype: list
        @return: A list of [(location, name), (location, name), ...] for each
                 preset that has an update available
    """
    _log.debug(_("Checking for device preset updates..."))
    
    updates = []
    
    if not location.endswith("/"):
        location = location + "/"
    
    f = urllib.request.urlopen(location + "presets.txt")
    
    try:
        for line in f.readlines():
            if not line.strip():
                continue
            
            parts = [part.strip() for part in line.split(",")]
            
            if len(parts) == 2:
                name, version = parts
                if name in _presets:
                    if _presets[name].version >= version:
                        _log.debug(("Device preset %(name)s is up to date") % {
                            "name": name,
                        })
                    else:
                        _log.debug(("Found updated device preset %(name)s") % {
                            "name": name,
                        })
                        try:
                            updates.append((location, name))
                        except Exception as e:
                            _log.error(("Error installing preset %(name)s " \
                                         "from %(location)s: %(error)s") % {
                                "name": name,
                                "location": location,
                                "error": str(e),
                            })
                else:
                    _log.debug(("Found new device preset %(name)s") % {
                        "name": name,
                    })
                    try:
                        updates.append((location, name))
                    except Exception as e:
                        _log.error(("Error installing preset %(name)s " \
                                     "from %(location)s: %(error)s") % {
                            "name": name,
                            "location": location,
                            "error": str(e),
                        })
            else:
                _log.warning(("Malformed plugin version line %(line)s") % {
                    "line": line,
                })
    except:
        _log.warning(("There was a problem accessing %(location)spresets.txt!") % {
            "location": location,
        })
    
    return updates

def check_and_install_updates(location = UPDATE_LOCATION):
    """
        Check for and install updated presets from a central server. This is
        equivalent to calling install_preset with each tuple returned from
        check_for_updates.
        
        @type location: str
        @param location: The directory where presets.txt and all preset files
                         can be found on the server
    """
    updates = check_for_updates(location)
    
    if updates:
        for loc, name in updates:
            install_preset(loc, name)
    else:
        _log.debug(_("All device presets are up to date!"))

# Automatically load presets - system, home, current path
for path in reversed(utils.get_search_paths()):
    full = os.path.join(path, "profiles")
    if os.path.exists(full):
        load_directory(full)

