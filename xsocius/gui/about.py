"""About box."""

import webbrowser

import wx
import wx.html

from xsocius.utils import NAME, VERSION, URL
from xsocius.gui.utils import get_icon

ABOUT = """
<html><body>
<table cellpadding="10">
<tr>
<td valign="TOP">
<p>&nbsp;</p>
<img src="%s" />
</td>
<td>
<h1>%s</h1>
<p>%s</p>
<p><a href="%s">%s</a></p>
<p>Copyright &copy; 2013 by Joel Burton &lt;joel@joelburton.com&gt;.</p>
<p>Powered by <a href="http://python.org">Python</a>, 
  <a href="http://wxpython.org">wxPython</a>, 
  and <a href="http://sleekxmpp.com">SleekXMPP</a>.</p>

<font color="#666666">
<p>
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
</p><p>
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
</p><p>
    You should have received a copy of the GNU General Public License
    along with this program.  If not, see
    <a href="http://www.gnu.org/licenses/">http://gnu.org/licenses</a>.
    </p>
 </font>
</body>
</html>
""" % (get_icon(NAME.lower()+'.gif'), NAME, VERSION, URL, URL)


class AboutHtmlWindow(wx.html.HtmlWindow):
    """HTML Window inside of about box."""

    def OnLinkClicked(self, link):
        addr = link.GetHref()
        webbrowser.open(addr)


class AboutBox(wx.Dialog):
    """About box dialog."""

    def __init__(self):
        if wx.Platform == "__WXMSW__":
            height = 530
        else:
            height = 430
        wx.Dialog.__init__(self, None, title="About...", size=(600, height))
        html = AboutHtmlWindow(self)
        html.SetPage(ABOUT)
        self.ShowModal()
        self.Destroy()
