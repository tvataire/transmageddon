# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# gst-fraction (taken from gst-python)
# Copyright (C) 2002 David I. Lehn
# Copyright (C) 2005-2010 Edward Hervey
# Copyright (C) 2012 Christian F.K. Schaller
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
# 

import sys
from gi.repository import GObject
# GObject.threads_init()
from gi.repository import GLib

class Fraction():
    def __init__(self, num, denom=1):
        self.num = num
        self.denom = denom

    def __repr__(self):
        return '<gst.Fraction %d/%d>' % (self.num, self.denom)

    def __eq__(self, other):
        if isinstance(other, Fraction):
            return self.num * other.denom == other.num * self.denom
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __mul__(self, other):
        if isinstance(other, Fraction):
            return Fraction(self.num * other.num,
                            self.denom * other.denom)
        elif isinstance(other, int):
            return Fraction(self.num * other, self.denom)
        raise TypeError

    __rmul__ = __mul__

    def __div__(self, other):
        if isinstance(other, Fraction):
            return Fraction(self.num * other.denom,
                            self.denom * other.num)
        elif isinstance(other, int):
            return Fraction(self.num, self.denom * other)
        return TypeError

    def __rdiv__(self, other):
        if isinstance(other, int):
            return Fraction(self.denom * other, self.num)
        return TypeError

    def __float__(self):
        return float(self.num) / float(self.denom)

try:
    dlsave = sys.getdlopenflags()
    from DLFCN import RTLD_GLOBAL, RTLD_LAZY
except AttributeError:
    # windows doesn't have sys.getdlopenflags()
    RTLD_GLOBAL = -1
    RTLD_LAZY = -1
except ImportError:
    RTLD_GLOBAL = -1
    RTLD_LAZY = -1
    import os
    osname = os.uname()[0]
    if osname == 'Linux' or osname == 'SunOS' or osname == 'FreeBSD' or osname == 'GNU/kFreeBSD' or osname == 'GNU':
        machinename = os.uname()[4]
        if machinename == 'mips' or machinename == 'mips64':
            RTLD_GLOBAL = 0x4
            RTLD_LAZY = 0x1
        else:
            RTLD_GLOBAL = 0x100
            RTLD_LAZY = 0x1
    elif osname == 'Darwin':
        RTLD_GLOBAL = 0x8
        RTLD_LAZY = 0x1
    del os
except:
    RTLD_GLOBAL = -1
    RTLD_LAZY = -1

if RTLD_GLOBAL != -1 and RTLD_LAZY != -1:
    sys.setdlopenflags(RTLD_LAZY | RTLD_GLOBAL)


