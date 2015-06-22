"""Puzzle note."""

import wx
import wx.lib.scrolledpanel as sp
from xsocius.gui.menu import BrowserMenuBar


class NoteWindow(wx.Frame):
    """Note window."""

    def __init__(self, body):
        body = body.replace("\r\n", "\n")
        print(body)
        wx.Frame.__init__(self, None, title='Note')

        self.SetMenuBar(BrowserMenuBar(self))

        panel = sp.ScrolledPanel(self)
        panel.SetupScrolling()

        sizer = wx.BoxSizer()
        text = wx.StaticText(panel, label=body)
        sizer.Add(text)
        panel.SetSizer(sizer)

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.Show()
        self.Raise()
        wx.GetApp().SetTopWindow(self)

    def OnClose(self, event):
        """Close and destroy."""

        self.Destroy()

    def OnQuit(self, event):
        """Quit application."""

        self.Destroy()
        wx.GetApp().OnQuit(event)
