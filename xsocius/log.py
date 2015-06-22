"""Logging system.

If we're running in console mode, we don't do anything unusual and
logging messages are emitted through Python's log module.

If we're not in console mode then we log to a file on disk
and replace the uncaught-exception-handler with one that (a)
prints to stderr [which is redirected to disk], writes a
separate crash file, and if possible pops up a wx dialog.
It then shows the send-debug-info screen and quits the
application.
"""

import sys
import os.path
import logging
import datetime
import traceback
from xsocius.utils import NAME

# Try to get wx and our bug reporting window but if we can't, it's ok

try:
    import wx
    import xsocius.gui.bugreport
    HAS_WX = True

except:
    HAS_WX = False


log_file = None
err_file = None

# If we're running in console mode, put us in "DEBUG MODE"

if hasattr(sys.stderr, 'isatty'):
    DEBUG_MODE = sys.stderr.isatty()

else:
    DEBUG_MODE = False


def oh_fuck(typ, val, tb):
    """Uncaught exception handler."""

    tbs = "".join(traceback.format_exception(typ, val, tb))
    sys.stderr.write(tbs)
    # write error to file
    try:
        with open(log_path('crash'), 'w') as f:
             f.write(tbs)
    except Exception:
        pass
 
    if HAS_WX:
        # write error to popup dialog
        dlg = wx.MessageDialog(
                None, 
                "A serious error has occurred: %s.\n\n\n" % val +
                tbs + 
                "\n\nAfter this message, you should have a chance" +
                " to report it to the developer, and then %s will quit.\n" % NAME,
                "Crash Report", 
                wx.ICON_HAND)
        dlg.ShowModal()
        dlg.Destroy()
        try:
            if not DEBUG_MODE:
                xsocius.gui.bugreport.showBugReport(
                        config=wx.GetApp().config,
                        error=tbs)
        except Exception:
            pass

    os._exit(1) # close the program

sys.excepthook = oh_fuck


def setup_logging():
    """Setup logging.

       If we're in DEBUG_MODE, log to console. Otherwise,
       log to file.
    """

    logging.captureWarnings(True)

    if not DEBUG_MODE:
        log_file = log_path('log')
        logging.basicConfig(filename=log_file,
                            level=logging.DEBUG, 
                            format="%(levelname)-8s %(message)s")
        return log_file

    else:
        logging.basicConfig(level=logging.DEBUG, 
                            format="%(levelname)-8s %(message)s")
        return None


def log_path(logtype):
    """Get path for a log file.

       Like "~/xsocius-2012-12-25-09-00-00-log.txt"
    """

    name = NAME.lower()
    dtime = datetime.datetime.today().strftime('%Y-%m-%d-%H-%M-%S')
    home = os.path.expanduser("~")
    fname = "{}-{}-{}.txt".format( name, dtime, logtype )
    return os.path.join(home, fname)
