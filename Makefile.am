ACLOCAL_AMFLAGS = -I common/m4 ${ACLOCAL_FLAGS}

SUBDIRS	= bin src common po profiles presets

@INTLTOOL_DESKTOP_RULE@

desktopdir = $(datadir)/applications
desktop_in_files = transmageddon.desktop.in.in
desktop_DATA = $(desktop_in_files:.desktop.in.in=.desktop)

icondir = $(datadir)/pixmaps
icon_DATA = transmageddon.svg

man_MANS = transmageddon.1

transmageddondir = $(datadir)/transmageddon
transmageddon_DATA = transmageddon.svg

EXTRA_DIST = \
	transmageddon.spec \
	transmageddon.spec.in \
	ChangeLog \
	autogen.sh \
	NEWS \
	AUTHORS \
	RELEASE \
	ABOUT-NLS \
	transmageddon.svg \
        transmageddon.1 \
	$(desktop_in_files) \
	$(INTLTOOL)


DISTCLEANFILES =                \
        intltool-extract        \
        intltool-merge          \
        intltool-update		\
	autoregen.sh		\
	config.log		\
	Makefile		\
	Makefile.in		\
	missing			\
	mkinstalldirs		\
	py-compile		\
	config.status		\
	install-sh		\
	configure \
	$(desktop_DATA)


EXTRA_DIST +=                    \
        intltool-extract.in     \
        intltool-merge.in       \
        intltool-update.in	\
	TODO

locale-uninstalled:
	if test -d po; then \
	    $(MAKE) -C po datadir=../$(top_builddir) install; \
	fi

locale-uninstalled-clean:
	@-rm -rf _trial_temp
	@-rm -rf $(top_builddir)/locale


all-local: locale-uninstalled
clean-local: locale-uninstalled-clean
