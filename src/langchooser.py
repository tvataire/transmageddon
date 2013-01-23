import os
from gi.repository import Gtk, GLib, Gst, GstTag

class languagechooser(Gtk.Dialog): 
   def __init__(self, parent): 
       self.languageui = Gtk.Builder()
       self.languageui.add_from_file("transmageddon-language-chooser.ui")
       langscroll = self.languageui.get_object("langscroll")
       cancelbutton = self.languageui.get_object("cancelbutton")
       selectbutton = self.languageui.get_object("selectbutton")

       self.languageui.connect_signals(self) # Initialize User Interface
       self.langcode=None # this will hold the selected language value

       store = Gtk.ListStore(str)
       self.langcodeList=GstTag.tag_get_language_codes()
       langcontents = []
       for item in self.langcodeList: 
           langcontents.append([GstTag.tag_get_language_name(item)])
       for act in langcontents:
           store.append([act[0]])
                           
       self.langview = Gtk.TreeView(store)
       self.langview.set_reorderable(False)
       self.langview.set_headers_visible(False)

       langscroll.add(self.langview)
       self.create_columns(self.langview)        
       self.languagewindow = self.languageui.get_object("languageui")
       self.languagewindow.set_modal(True)
       self.languagewindow.set_transient_for(parent)

       self.languagewindow.show_all()

   def create_columns(self, treeView):
       rendererText = Gtk.CellRendererText()
       column = Gtk.TreeViewColumn(None, rendererText, text=0)
       column.set_sort_indicator(False)
       self.langview.append_column(column)

   def on_cancelbutton_clicked(self, widget):
       self.languagewindow.destroy()


   def on_selectbutton_clicked(self, widget):
       language=self.langview.get_selection()
       (model, pathlist) = language.get_selected_rows()
       for path in pathlist :
           tree_iter = model.get_iter(path)
           value = model.get_value(tree_iter,0)
           numvalue=path.to_string()
           self.langcode=self.langcodeList[int(numvalue)]
       self.languagewindow.destroy()


