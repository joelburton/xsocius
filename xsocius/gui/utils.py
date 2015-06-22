"""Common utils for GUI component."""

import os
from pkg_resources import resource_filename

import wx

# Different OS implementations seem to default to different scaled fonts;
# so there's a roughly consistent size, we introduce a scale factor.

if wx.Platform == '__WXMSW__':
    SCALE = .80
elif wx.Platform == '__WXGTK__':
    SCALE = .75
elif wx.Platform == '__WXMAC__':
    SCALE = 1.0
else:
    # WTF are we?
    SCALE = 1.0


def font_scale(size):
    return size * SCALE


def makeText(window, txt):
    """Add static text."""

    _ = wx.StaticText(window, wx.ID_ANY, txt)
    return _


def makeHeading(window, txt):
    """Add heading static text."""

    _ = wx.StaticText(window, wx.ID_ANY, txt)
    _.SetFont(wx.Font(font_scale(12), wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.BOLD))
    return _


def makeHint(window, txt):
    """Add light-grey static text."""

    _ = wx.StaticText(window, wx.ID_ANY, txt)
    _.SetFont(wx.Font(font_scale(10), wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.NORMAL))
    _.SetForegroundColour("#444444")
    return _


def _get_resource(sect, fname):
    """Return resource file.

       Linux and eggs use resource_filename; others use local path.
    """

    try:
        return resource_filename("xsocius", "%s/%s" % (sect, fname))
    except NotImplementedError as e:
        return os.path.abspath("%s/%s" % (sect, fname))


def get_icon(fname):
    """Return icon."""

    return _get_resource('icons', fname)


def get_tips(fname):
    """Return tips file."""

    return _get_resource('tips', fname)


def get_sound(fname):
    """Return sound file."""

    return _get_resource('sounds', fname)


def get_help(fname):
    """Return help file."""

    return _get_resource('help', fname)
