#!/opt/local/bin/python3.3

"""Xsocius runner."""

# DO NOT EDIT THIS FILE OR ADD ANY LOGIC TO IT.
# If you do, you must release a new minor version (1.x.0), since
# patch versions cannot get a new version of this file. 
# 
# Put any logic in the gui.app.runApp instead.

import wx
import wx.adv
from xsocius.gui.utils import get_icon
from xsocius.utils import NAME

# We want to put up a splash screen ASAP, so let's do it before we
# even import the main stuff.

img = wx.Image(get_icon("%s.gif" % NAME.lower()))
bmp = img.ConvertToBitmap()
app = wx.App()
splash = wx.adv.SplashScreen(
        bmp, 
        wx.adv.SPLASH_CENTRE_ON_SCREEN|wx.adv.SPLASH_TIMEOUT, 
        100,   # 1/10th of a second
        None)
del(app)

import xsocius.gui.app

xsocius.gui.app.runApp()
