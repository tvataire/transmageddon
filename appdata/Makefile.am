#AppData
@APPDATA_XML_RULES@
@INTLTOOL_XML_RULE@

appdata_in_files = transmageddon.appdata.xml.in
appdata_XML = $(appdata_in_files:.xml.in=.xml)

dist_noinst_DATA = \
       $(appdata_in_files) 

EXTRA_DIST = $(appdata_in_files)
CLEANFILES = $(appdata_XML)


