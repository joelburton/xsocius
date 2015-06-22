"""OneAcross.com crossword hint system."""

import webbrowser
import urllib.request, urllib.parse, urllib.error

import wx
try:
    import wx.html2 as html2
except ImportError:
    html2 = None

from xsocius.gui.browser import BrowserWindow


def OpenOneAcross(clue, word):
    """Open OneAcross."""
    
    data = urllib.parse.urlencode({"c0":clue,  "p0": word})
    url = "http://oneacross.com/cgi-bin/search_banner.cgi?%s" % data
    
    if wx.GetApp().config.internal_browser and html2 is not None:
        title = "One Across Lookup: %s" % clue
        BrowserWindow(url, title)
    else:
        webbrowser.open(url, new=2)
