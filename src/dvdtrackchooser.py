import os,datetime, sys
from gi.repository import Gtk, GLib, Gst, GstTag
from gi.repository import GUdev

class dvdtrackchooser(Gtk.Dialog): 
   def __init__(self, parent): 
       self.dvdpickui = Gtk.Builder()
       self.dvdpickui.add_from_file("transmageddon-dvdtrack-chooser.ui")
       dvdscroll = self.dvdpickui.get_object("dvdscroll")
       cancelbutton = self.dvdpickui.get_object("cancelbutton")
       selectbutton = self.dvdpickui.get_object("selectbutton")

       self.cachedir=GLib.get_user_cache_dir()+"/transmageddon"
       CheckDir = os.path.isdir(self.cachedir)
       if CheckDir == (False):
           os.mkdir(self.cachedir)
       sys.path.append(self.cachedir)

       self.dvdpickui.connect_signals(self) # Initialize User Interface
       self.dvdtrack=None # this will hold the selected DVD track value
       self.isdvd=False
       self.dvdtitle=False

       store = Gtk.ListStore(str, int)
       # udev code to find DVD drive on system - This code needs to go into Transmageddon proper
       client = GUdev.Client(subsystems=['block'])
       for device in client.query_by_subsystem("block"):
           if device.has_property("ID_CDROM"):
               self.dvdpath=device.get_device_file()


       # use lsdvd tool to get DVD track information
       self.Title = False
       self.Tracks = False
       self.dvdread(self.dvdpath)
       scounter=0
       longesttime = 0
       self.listoftracks=[]
       languages=[]
       while scounter < len(self.Tracks):
           tcounter=0
           language=""
           langcodes=[]
           self.ix=int(self.Tracks[scounter]['ix'])
           while tcounter <  len(self.Tracks[scounter]['audio']):
               if self.Tracks[scounter]['audio']:
                   if GstTag.tag_check_language_code(self.Tracks[scounter]['audio'][tcounter]['langcode']):
                       if self.Tracks[scounter]['audio'][tcounter]['langcode'] not in langcodes:
                           langcodes.append(self.Tracks[scounter]['audio'][tcounter]['langcode'])
                           language=language + GstTag.tag_get_language_name(self.Tracks[scounter]['audio'][tcounter]['langcode']) + ", "
               tcounter=tcounter+1

           languages.append(language)
           
           # create a string to push into the listview
           self.listoftracks.append(_("Title:b ") + str(scounter) + ", " + _("Languages: ") + languages[scounter] + _(" Length: ") + str(round((self.Tracks[scounter]['length']/60), 2)) + " Minutes")

           # For testing purposes look for longest track
           scounter=scounter+1

       x=1
       for act in self.listoftracks:
           store.append([act,x])
           x=x+1
                           
       self.dvdtrackview = Gtk.TreeView(store)
       self.dvdtrackview.set_reorderable(False)
       self.dvdtrackview.set_headers_visible(False)

       dvdscroll.add(self.dvdtrackview)
       self.create_columns(self.dvdtrackview)        
       self.dvdwindow = self.dvdpickui.get_object("dvdpickui")
       self.dvdwindow.set_modal(True)
       self.dvdwindow.set_transient_for(parent)

       self.dvdwindow.show_all()

   def create_columns(self, treeView):
       rendererText = Gtk.CellRendererText()
       column = Gtk.TreeViewColumn(None, rendererText, text=0)
       column.set_sort_indicator(False)
       self.dvdtrackview.append_column(column)

   def on_cancelbutton_clicked(self, widget):
       self.isdvd=False
       self.dvdwindow.destroy()


   def on_selectbutton_clicked(self, widget):
       dvdtitle = self.dvdtrackview.get_selection()
       (model, pathlist) = dvdtitle.get_selected_rows()
       for path in pathlist :
           tree_iter = model.get_iter(path)
           value = model.get_value(tree_iter,1)
           self.dvdtitle=value
           print("TITLE IS " +str(value))
           self.isdvd=True
       self.dvdwindow.destroy()

   def dvdread(self, device):
        file = open('%s/lsdvdout.py' % self.cachedir, 'w')
        file.write('#!/usr/bin/python3\n')
        file.write('# -*- coding: ISO-8859-1 -*-\n')
        file.close()
        cmd = 'lsdvd -a -Oy %s >> %s/lsdvdout.py' % (device, self.cachedir);
        os.system(cmd)

        from lsdvdout import lsdvd
        self.Title = lsdvd['title']
        self.Tracks = lsdvd['track']

# Setup i18n support
import locale
from gettext import gettext as _
import gettext
import signal
  
#Set up i18n
gettext.bindtextdomain("transmageddon","../../share/locale")
gettext.textdomain("transmageddon")

if __name__ == "__main__":
    app = dvdtrackchooser()
