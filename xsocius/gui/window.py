"""Base window for puzzle windows and dummy window."""

import logging

import wx

from xsocius.gui.menu import DummyMenuBar
from xsocius.gui.share import JoinWindowMixin
from xsocius.utils import NAME, VERSION
from xsocius.gui.utils import get_icon, makeHint


class BaseWindow(wx.Frame, JoinWindowMixin):
    """Base window; used for both empty-window and real puzzle window."""

    puzzle = None
    board = None
    dummy = False

    def __init__(self,
                 title,
                 pos=(1, 1),
                 style=wx.DEFAULT_FRAME_STYLE,
                 size=(700, 500)):
        wx.Frame.__init__(self,
                          None,
                          wx.ID_ANY,
                          title,
                          pos=pos,
                          style=style,
                          size=size)

        JoinWindowMixin.__init__(self)

        # Doesn't appear on OSX as of wx2.9
        path = get_icon("generic.png")
        icon = wx.Icon(path, wx.BITMAP_TYPE_PNG)
        self.SetIcon(icon)

        self.Bind(wx.EVT_CLOSE, self.OnClose)


class DummyWindow(BaseWindow):
    """Dummy window.

       Not a puzzle window, but a window that prompts you to open a
       puzzle in different ways.

       Show the program icon, name, a beta message, and a row
       of buttons for opening puzzles.
    """

    dummy = True

    def __init__(self):
        logging.debug("Making dummy window")

        BaseWindow.__init__(self, title=NAME, size=(200, 200),
                            style=wx.DEFAULT_FRAME_STYLE & ~(
                            wx.RESIZE_BORDER | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX)
                            )

        app = wx.GetApp()

        self.SetMenuBar(DummyMenuBar(self))

        panel = wx.Panel(self)

        icon = wx.StaticBitmap(panel,
                               label=wx.Bitmap(get_icon(
                                   "%s.gif" % NAME.lower())))

        welcome = wx.StaticText(panel, wx.ID_ANY,
                                label="Welcome to {} {}".format(NAME, VERSION))
        welcome.SetFont(wx.Font(18,
                                wx.FONTFAMILY_DEFAULT,
                                wx.FONTSTYLE_NORMAL,
                                wx.FONTWEIGHT_BOLD))
        welcome.SetForegroundColour("#444444")
        beta = makeHint(panel,
                        "BETA VERSION: Please use Bug Report in Help menu and "
                        + "send reports/feedback to joel@joelburton.com.")

        # openhelp = wx.Button(panel, wx.ID_ANY, label="Open Help")
        openfile = wx.Button(panel, wx.ID_ANY, label="Open File Puzzle")
        openweb = wx.Button(panel, wx.ID_ANY, label="Open Web Puzzle")
        openjoin = wx.Button(panel, wx.ID_ANY, label="Join Puzzle with Friend")
        # self.Bind(wx.EVT_BUTTON, app.OnHelp, openhelp)
        self.Bind(wx.EVT_BUTTON, app.OnWebChooser, openweb)
        self.Bind(wx.EVT_BUTTON, app.OnOpen, openfile)
        self.Bind(wx.EVT_BUTTON, self.OnJoin, openjoin)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Until we fix the can't show help before window but, let's hide this
        # sizer.Add(openhelp, 0, wx.LEFT|wx.BOTTOM, 30)
        # sizer.AddSpacer(10)
        sizer.Add(openfile, 0, wx.BOTTOM, 30)
        sizer.AddSpacer(10)
        sizer.Add(openweb, 0, wx.BOTTOM, 30)
        sizer.AddSpacer(10)
        sizer.Add(openjoin, 0, wx.RIGHT | wx.BOTTOM, 30)

        sizer1 = wx.BoxSizer(wx.VERTICAL)
        sizer1.Add(icon, 0,
                   wx.TOP | wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL, 30)
        sizer1.Add(welcome, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 30)
        sizer1.Add(beta, 0,
                   wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL, 30)
        sizer1.AddSpacer(30)
        sizer1.Add(sizer, 0, wx.ALIGN_CENTER_HORIZONTAL)

        panel.SetSizer(sizer1)
        panel.Raise()
        panel.Fit()
        panel.Show()

        sizer1.Fit(self)
        self.CenterOnScreen()
        self.Show()

        logging.debug("Is shown: %s" % self.IsShown())

    def OnClose(self, event):
        """Close dummy window."""

        wx.GetApp().config.filehistory.RemoveMenu(self.RecentMenu)
        assert self.Destroy()
