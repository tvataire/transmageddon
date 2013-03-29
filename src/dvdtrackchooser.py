import os,datetime
from gi.repository import Gtk, GLib, Gst, GstTag
from gi.repository import GUdev

class dvdtrackchooser(Gtk.Dialog): 
   def __init__(self, parent): 
       self.dvdpickui = Gtk.Builder()
       self.dvdpickui.add_from_file("transmageddon-dvdtrack-chooser.ui")
       dvdscroll = self.dvdpickui.get_object("dvdscroll")
       cancelbutton = self.dvdpickui.get_object("cancelbutton")
       selectbutton = self.dvdpickui.get_object("selectbutton")

       self.dvdpickui.connect_signals(self) # Initialize User Interface
       self.dvdtrack=None # this will hold the selected DVD track value

       store = Gtk.ListStore(str)
       # udev code to find DVD drive on system - This code needs to go into Transmageddon proper
       client = GUdev.Client(subsystems=['block'])
       for device in client.query_by_subsystem("block"):
           if device.has_property("ID_CDROM"):
               self.path=device.get_device_file()


       # use lsdvd tool to get DVD track information
       self.Title = False
       self.Tracks = False
       self.dvdread(self.path)
       print(self.Title)
       scounter=0
       longesttime = 0
       self.listoftracks=[]
       while scounter < len(self.Tracks):
           tcounter=0
           self.ix=int(self.Tracks[scounter]['ix'])
           while tcounter <  len(self.Tracks[scounter]['audio']):
               if self.Tracks[scounter]['audio']:
                   if GstTag.tag_check_language_code(self.Tracks[scounter]['audio'][tcounter]['langcode']):
                       self.listoftracks.append("Track " + str(scounter) + " " + GstTag.tag_get_language_name(self.Tracks[scounter]['audio'][tcounter]['langcode']) + " " +(self.Tracks[scounter]['audio'][tcounter]['format']+ " " +str((self.Tracks[scounter]['audio'][tcounter]['channels']))))
               tcounter=tcounter+1

           # For testing purposes look for longest track
           lenght=self.Tracks[scounter]['length']
           if lenght > longesttime:
               longesttime = lenght
               self.longestrack = self.ix
           time=str(datetime.timedelta(seconds=lenght))
           scounter=scounter+1
       print("THE longest track " + str(self.longestrack))   


       for act in self.listoftracks:
           store.append([act])
                           
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
       self.dvdwindow.destroy()


   def on_selectbutton_clicked(self, widget):
       dvdtrack=self.dvdtrackview.get_selection()
       (model, pathlist) = dvdtrack.get_selected_rows()
       for path in pathlist :
           tree_iter = model.get_iter(path)
           value = model.get_value(tree_iter,0)
           numvalue=path.to_string()
           self.dvdtrack=1 #FIXME
       self.dvdwindow.destroy()

   def dvdread(self, device):
        file = open('lsdvdout.py', 'w')
        file.write('#!/usr/bin/python3\n')
        file.write('# -*- coding: ISO-8859-1 -*-\n')
        file.close()
        cmd = 'lsdvd -a -Oy %s >> lsdvdout.py' % (device);
        os.system(cmd)
        # try:
        from lsdvdout import lsdvd
        self.Title = lsdvd['title']
        self.Tracks = lsdvd['track']

if __name__ == "__main__":
    app = dvdtrackchooser()
