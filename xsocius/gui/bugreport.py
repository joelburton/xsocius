"""Bug report window."""

import sys
import pprint
import logging

import io
import wx
import wx.lib.dialogs
import xsocius.log
from xsocius.utils import NAME, VERSION


def config_to_text(config):
    """Return string of config settings along with web openers."""

    out = io.StringIO()

    for prop, sect, default, descrip in config._PROPERTIES:
        if type(default) == type(0):
            f = config.config.ReadInt
        elif type(default) == type(""):
            f = config.config.Read
        elif type(default) == type(False):
            f = config.config.ReadBool
        else:
            continue  # shouldn't get here

        val = f("/%s/%s" % (sect, prop))
        if prop == "password":
            val = "***"
        print("%s.%s = %s" % (sect, prop, val), file=out)

    print(pprint.pprint(config.getWebOpeners(include_disabled=True), out))

    out.seek(0)
    return out.read()


def _read_file(fname):
    """Safely read a file.
    
    If we're in console mode, the logs are set to None, so we'll just
    read nothing for them.
    """

    if fname:
        with open(fname) as f:
            return f.read()


def showBugReport(config, error=""):
    logging.debug("Show bug report.")

    sys.stderr.flush()

    _ = {'wxver': wx.version(),
         'wxplatform': wx.PlatformInfo,
         'pyver': sys.version,
         'prefs': config_to_text(config),
         'logs': _read_file(xsocius.log.log_file),
         'name': NAME,
         'version': VERSION,
         'error': error,
         }

    body = """BUG REPORT TEMPLATE:

- Copy and paste this whole text into an email message.
- Fill in the three section below.
- Send to joel@joelburton.com.

DESCRIPTION OF PROBLEM:



WHAT YOU EXPECTED TO HAPPEN:



WHAT DID HAPPEN:

%(error)s

--- Do not change info below this line ---

SYSTEM INFO:
%(name)s %(version)s
wxplatform = %(wxplatform)s
wxver = %(wxver)s
python = %(pyver)s


PREFERENCES:
%(prefs)s


LOG:
%(logs)s

""" % _
    dlg = wx.lib.dialogs.ScrolledMessageDialog(None, body,
                                               "Bug Report Details", size=(800, 500))
    dlg.ShowModal()
    dlg.Destroy()
