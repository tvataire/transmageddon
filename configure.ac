AC_PREREQ([2.63])

dnl initialize autoconf
dnl when going to/from release please set the nano (fourth number) right !
dnl releases only do Wall, cvs and prerelease does Werror too
AC_INIT([transmageddon],
        [0.22-test],
        [https://bugzilla.gnome.org/enter_bug.cgi?product=transmageddon],
        [transmageddon],
        [http://www.linuxrising.org/transmageddon])

AC_CONFIG_SRCDIR([src/transmageddon.py])
AC_CONFIG_MACRO_DIR([m4])

dnl initialize automake
AM_INIT_AUTOMAKE([1.11 no-dist-gzip dist-xz])

dnl enable maintainer mode option
AM_MAINTAINER_MODE([enable])

AC_SUBST_FILE(AUTHORS)
AUTHORS=$srcdir/AUTHORS

dnl Note for packagers
dnl The following requirements are run-time requirements,
dnl make sure you don't forget them, even though you're able to
dnl build pitivi without them.
dnl
dnl For a more exhaustive list of checks, you can have a look at
dnl the runtime checks in pitivi/check.py

AC_SUBST(GST_REQ, 0.11.0)

AS_AC_EXPAND(LIBDIR, $libdir)
AC_MSG_NOTICE(Storing library files in $LIBDIR)

AS_AC_EXPAND(DATADIR, $datadir)
AC_MSG_NOTICE(Storing data files in $DATADIR)

AS_AC_EXPAND(SYSCONFDIR, $sysconfdir)
AC_MSG_NOTICE(Storing configuration files in $SYSCONFDIR)

AS_AC_EXPAND(LOCALSTATEDIR, $localstatedir)
AC_MSG_NOTICE(Using localstatedir $LOCALSTATEDIR)

dnl check for python
AS_PATH_PYTHON(2.5)

dnl enable i18n
ALL_LINGUAS="pl"
GETTEXT_PACKAGE="transmageddon"
AC_SUBST([GETTEXT_PACKAGE])
AC_DEFINE_UNQUOTED([GETTEXT_PACKAGE], "$GETTEXT_PACKAGE", [Gettext package])
AM_GLIB_GNU_GETTEXT
IT_PROG_INTLTOOL([0.35.0])

CONFIGURED_PYTHONPATH=$PYTHONPATH
AC_SUBST(CONFIGURED_PYTHONPATH)

AC_CONFIG_FILES([bin/transmageddon], [chmod +x bin/transmageddon])

dnl output stuff
AC_CONFIG_FILES([
Makefile
bin/Makefile
common/Makefile
common/m4/Makefile
src/about.py
src/Makefile
profiles/Makefile
presets/Makefile
po/Makefile.in
transmageddon.spec
transmageddon.desktop.in
])
AC_OUTPUT
