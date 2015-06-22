"""GUI and wx-specific code for opening web puzzles."""

import sys
import datetime

import wx
import wx.adv
import wx.lib.mixins.listctrl as listmix
import wx.lib.agw.pybusyinfo as PBI

from xsocius.gui.utils import get_icon

from xsocius.web import WebOpener, WebPuzzleOpenException

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 
             'Saturday', 'Sunday' ]

class WebOpenList(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    """List of websites.
    
    A one column list with an icon for each site on the left.
    """

    def __init__(self, parent, sites):
        wx.ListCtrl.__init__(self, 
                parent, 
                style=( wx.LC_REPORT
                       |wx.LC_SINGLE_SEL
                       |wx.SUNKEN_BORDER
                       |wx.LC_NO_HEADER),
                size=(150, 350))
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        
        self.InsertColumn(0, "Site")
        
        self.imgl = wx.ImageList(16, 16)
        self.SetImageList(self.imgl, wx.IMAGE_LIST_SMALL)

        for puz in sites:
            idx = self.InsertItem(
                       sys.maxsize, 
                       puz['name'], 
                       self.imgl.Add(wx.Bitmap(get_icon(puz['icon']))))
            self.enableItem(idx, puz['enabled'])
        
        # Make size dynamic to list
        height = sum( 
                [ self.GetItemRect(i).height 
                        for i in range(self.GetItemCount()) ]) 
        self.SetMinSize((300, height+10))
        self.resizeLastColumn(1)


    def enableItem(self, idx, enable=True):
        """Enable web opener in list."""

        item = self.GetItem(idx)
        if enable:
            color = (0, 0, 0)
        else:
            color = (160, 160, 160)
        item.SetTextColour(color)
        self.SetItem(item)



class WebOpenDialog(wx.Dialog):
    """Dialog for websites.

       Show list of websites with open/cancel button.
    """

    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, title="Select Web Puzzle")

        panel = wx.Panel(self, wx.ID_ANY)
        
        sizer = wx.BoxSizer(wx.VERTICAL)    # outermost
        sizer2 = wx.BoxSizer(wx.HORIZONTAL) # list / calendar+desc
        sizer3 = wx.BoxSizer(wx.VERTICAL)   # calendar / desc

        self.caldesc = wx.StaticText(panel, wx.ID_ANY, 
                "Start for Search Backwards:")
        sizer3.Add(self.caldesc, 0, wx.RIGHT|wx.BOTTOM|wx.TOP, 10)
        self.cal = wx.adv.CalendarCtrl(
                panel, 
                wx.ID_ANY, 
                wx.DateTime.Today(),
                style=wx.adv.CAL_MONDAY_FIRST)
        sizer3.Add(self.cal, 0, wx.RIGHT|wx.BOTTOM, 10)

        config = wx.GetApp().config
        self.sites = config.getWebOpeners()
        self.sitelist = slist = WebOpenList(panel, self.sites)
        sizer2.Add(slist, 1, wx.ALL|wx.EXPAND, 10)
        
        sizer2.Add(sizer3)
        sizer.Add(sizer2)
        
        self.desc = wx.StaticText(panel, wx.ID_ANY, "")
        sizer.Add(self.desc, 0, wx.LEFT|wx.RIGHT, 10)
        self.days = wx.StaticText(panel) 
        sizer.AddSpacer(5)

        _fontsize = 9
        if wx.Platform == "__WXMSW__":
            _fontsize = 8

        sizer.Add(self.days, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, 10)
        self.days.SetFont(wx.Font(
                    _fontsize, 
                    wx.FONTFAMILY_DEFAULT, 
                    wx.FONTSTYLE_NORMAL, 
                    wx.FONTWEIGHT_NORMAL))
        self.days.SetForegroundColour("#444444")

        # Add Ok/Cancel buttons
        btnsizer = wx.StdDialogButtonSizer()
        cancel = wx.Button(panel, wx.ID_CANCEL)
        btnsizer.AddButton(cancel)
        self.ok = ok = wx.Button(panel, wx.ID_OK)
        btnsizer.AddButton(ok)
        ok.SetDefault()
        ok.Enable(False)
        sizer.Add(btnsizer, flag=wx.ALIGN_RIGHT)
        btnsizer.Realize()
        
        panel.SetSizer(sizer)
        sizer.Fit(self)
        self.CenterOnScreen()
        
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, slist)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected, slist)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated, slist)
        
        slist.SetFocus()
        slist.Focus(0)
        slist.Select(0) 


    def OnItemSelected(self, event):
        """Item selected; allow OK button."""

        self.ok.Enable(True)
        idx = event.GetIndex()
        self.desc.SetLabel(self.sites[idx]['desc'])
        days = ", ".join(
                [ DAY_NAMES[int(i)-1] for i in self.sites[idx]['days'] ] )
        self.days.SetLabel("New puzzles expected: %s." % days)
        

    def OnItemDeselected(self, event):
        """Item deselected; disallow OK button."""

        self.ok.Enable(False)


    def OnItemActivated(self, event):
        """Handle doubleclick/Enter."""
        
        self.EndModal(wx.ID_OK)



def ShowWebOpenGUI():
    """Show web opener dialog and return chosen site # and date."""

    dlg = WebOpenDialog(None)
    result = dlg.ShowModal()
    dlg.Destroy()
    
    if result == wx.ID_OK:
        wxdate = dlg.cal.GetDate()
        date = datetime.date(wxdate.year, wxdate.month+1, wxdate.day)
        return dlg.sitelist.GetFirstSelected(), date
    else:
        return (None, None)
        

def WebOpenGUI(idx, startat=None):
    """Retrieve puzzle from web."""

    busy = PBI.PyBusyInfo("Opening Web Puzzle")
    wx.Yield() # Fixes bug that doesn't show busy box on GTK.
    config = wx.GetApp().config
    site = config.getWebOpeners()[idx]

    url, days, name = site['url'], site['days'], site['name']
    days = [int(d) for d in list(days)]

    directory = config.getCrosswordsDir()
    cookiefile = config.getSupportDir() + "/cookies.txt"

    try:
        fname = WebOpener(name, 
                          days, 
                          url, 
                          directory, 
                          startat, 
                          cookiefile=cookiefile)

    except WebPuzzleOpenException as e:
        # Error happened, show dialog with message and return without
        # filename
        dlg = wx.MessageDialog(None, 
                "A puzzle could not be successfully downloaded: %s" % e,
                "Web Error", 
                wx.OK | wx.ICON_ERROR )
        dlg.ShowModal()
        dlg.Destroy()
        return

    # Return filename of downloaded crossword puzzle on disk
    return fname


if __name__ == "__main__":
    sys.path.append('/Users/joel/programming/xsocius')
    from xsocius.gui.config import XsociusConfig

    app = wx.App(None)
    app.config = XsociusConfig()

    chosen, startdate = ShowWebOpenGUI()
    if chosen is not None:
        print(WebOpenGUI(chosen, startdate))
