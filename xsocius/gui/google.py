"""OneAcross.com crossword hint system."""

import webbrowser
import urllib.request
import urllib.parse
import urllib.error

import wx

try:
    import wx.html2 as html2
except ImportError:
    html2 = None

from xsocius.gui.browser import BrowserWindow


def OpenGoogle(clue, word):
    """Open Google."""

    data = urllib.parse.urlencode({"q": clue + " " + word})
    url = "http://www.google.com/search?%s" % data

    if wx.GetApp().config.internal_browser and html2 is not None:
        title = "Google Lookup: %s" % word
        BrowserWindow(url, title)
    else:
        webbrowser.open(url, new=2)
