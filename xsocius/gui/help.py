#!/usr/bin/env python

"""Help system."""

import urllib.request, urllib.parse, urllib.error
import webbrowser
import logging

import wx
try:
    import wx.html2 as html2
except ImportError:
    html2 = None

from xsocius.utils import NAME
from xsocius.gui.browser import BrowserWindow
from xsocius.gui.utils import get_help


def ShowHelp():
    """Show HTML help file."""

    url = "file:///" + urllib.parse.quote(get_help('index.html'))
        
    if html2 is not None:
        title = "%s Help" % NAME
        logging.info("Opening BrowserWindow at %s", url)
        bw = BrowserWindow(url, title)
    else:
        logging.info("Opening web browser at %s", url)
        webbrowser.open(url, new=2)


if __name__ == "__main__":
    app = wx.App()
    ShowHelp()
    app.MainLoop()
