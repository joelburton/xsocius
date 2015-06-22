"""Web browser."""

import wx
from xsocius.gui.menu import BrowserMenuBar

class BrowserWindow(wx.Frame):
    """Internal browser window."""

    def __init__(self, url, title):
        wx.Frame.__init__(self, None, size=(950, 650), title=title)
        
        self.SetMenuBar(BrowserMenuBar(self))

        webview = wx.html2.WebView.New(self)

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        webview.Bind(wx.html2.EVT_WEBVIEW_ERROR, self.OnError)

        webview.LoadURL(url)
        self.Show()
        self.Raise()
        wx.GetApp().SetTopWindow(self)


    def OnClose(self, event):
        """Close and destroy."""

        self.Destroy()


    def OnError(self, event):
        """Report web errors."""

        dlg = wx.MessageDialog(None, 
                "The web connection could not be completed.",
                "Network or Site Error", wx.OK | wx.ICON_ERROR )
        dlg.ShowModal()
        dlg.Destroy()
        self.Destroy()

    def OnQuit(self, event):
        """Quit application."""

        self.Destroy()
        wx.GetApp().OnQuit(event)


if __name__ == "__main__":
    import wx.html2
    app = wx.App()
    app.OnHelp = app.OnAbout = None
    BrowserWindow("http://foo.yahoo.com/asasa", "Yahoo")
    app.MainLoop()
