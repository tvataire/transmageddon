
presetdir = $(datadir)/transmageddon/presets
xmldir = $(datadir)/transmageddon/presets

xml_in_files = ipod.xml.in ps3.xml linux-computer.xml.in n800.xml.in krzr-k1v.xml.in n770.xml.in
xml_DATA = $(xml_in_files:.xml.in=.xml)

@INTLTOOL_XML_RULE@

EXTRA_DIST = $(xml_in_files) $(xml_DATA)
