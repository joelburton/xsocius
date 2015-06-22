"""
Xsocius

Can play crosswords in Across Lite format, either alone or
collaboratively.
"""

import sys
import logging
import atexit

import wx
import wx.adv
import xsocius.log
from xsocius.utils import NAME
from xsocius.puzzle import Puzzle, DiagramlessPuzzleFormatError
from xsocius.gui.about import AboutBox
from xsocius.gui.config import XsociusConfig
from xsocius.gui.window import DummyWindow
from xsocius.gui.puzzle import PuzzleWindow
from xsocius.gui.web import WebOpenGUI, ShowWebOpenGUI
from xsocius.gui.help import ShowHelp
from xsocius.gui.prefs import showPrefsDialog
from xsocius.gui.upgrade import prompt_update_version, newest_version_info
from xsocius.gui.utils import get_tips
from xsocius.gui.bugreport import showBugReport
from xsocius.acrosslite import PuzzleFormatError


class XsociusApp(wx.App):
    """Xsocius application."""

    windows = []
    config = None
    dummy = None

    def OnInit(self):
        """Finish setup of application."""

        self.SetAppName(NAME)

        # Splash screen 
        # img = wx.Image(get_icon("%s.gif" % NAME.lower()))
        # bmp = img.ConvertToBitmap()
        # splash = wx.adv.SplashScreen(bmp, wx.adv.SPLASH_CENTRE_ON_SCREEN, 1000, None)

        self.config = XsociusConfig()

        # Get newest version, if applicable
        if self.config.check_upgrades:
            newest, change, date = newest_version_info()

        # Get rid of splash screen
        # splash.Close()
        # splash.Destroy()
        # wx.Yield()

        # Show upgrades box, if applicable
        if self.config.check_upgrades:
            prompt_update_version(None, newest, change, date)

        # Show tip-of-day box

        self.tip_of_the_day = wx.adv.CreateFileTipProvider(
            get_tips("%s.txt" % NAME.lower()), self.config.tips_index)
        if self.config.show_tips:
            wx.CallAfter(self.show_tip_of_the_day)

        # Open any puzzle files passed on command-line

        logging.debug("sys.argv=%s", sys.argv)
        for path in sys.argv[1:]:
            logging.info("Opening from argv: %s", path)
            try:
                self.open_puzzle(path)
            except IOError:
                dlg = wx.MessageDialog(None, "Cannot open file requested on"
                                             " command line:\n%s." % path,
                                       "File Open Error", wx.OK | wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()

        # If our preferences say to do so, re-open windows

        if self.config.reopen:
            logging.debug("trying to reopen")
            for path in self.config.unpersistWindows():
                try:
                    self.open_puzzle(path)
                except IOError as e:
                    logging.warning("Cannot unpersist window: %s: %s", path, e)

        # Check our config to see what we should do on open
        # (show web dialog, file dialog, open most recent puzzle, or nothing)
        logging.debug("check to see what to do on open")

        if not self.windows:
            method = self.config.openmethod
            if method == "web":
                self.OnWebChooser(None)
            elif method == "file":
                self.OnOpen(None)
            elif method == "none":
                pass
            elif method == "last":
                numrecent = self.config.filehistory.GetNoHistoryFiles()
                if numrecent >= 1:
                    path = self.config.filehistory.GetHistoryFile(0)
                    try:
                        self.open_puzzle(path)
                    except IOError:
                        logging.warning(
                            "Cannot re-open last puzzle: %s.", path)
            elif method == "join":
                self.OpenDummy().OnJoin(None)
            else:
                raise Exception("Unknown open method")

                # In order for us to have a UI on Windows/Linux, we need a window
        # open even if there's no open puzzle. So we create a dummy window.
        # If no puzzle window got opened, show the dummy.

        if not self.windows:
            self.OpenDummy()

        # This catches events when the app is asked to activate by some other
        # process
        self.Bind(wx.EVT_ACTIVATE_APP, self.OnActivate)
        logging.debug("Leaving OnInit")
        return True

    def show_tip_of_the_day(self):
        """Show Tip of Day box.

           Record prefs of show-box and where it left off.
        """

        self.config.show_tips = wx.adv.ShowTip(
            None, self.tip_of_the_day, self.config.show_tips)
        self.config.tips_index = self.tip_of_the_day.CurrentTip

    def OpenDummy(self):
        """Open dummy window."""

        dummy = DummyWindow()
        self.windows.append(dummy)
        dummy.Show()
        dummy.Raise()
        self.SetTopWindow(dummy)
        return dummy

    def OnExit(self):
        """Exiting app."""

        # Nothing special needed.
        # Kept around in case code needed here, but for now this 
        # will just delegate to superclass.
        return super().OnExit()

    def NewWindow(self, title, size, minsize):
        """Open a new window."""

        if not self.windows:
            x = 10
            y = 30
        elif self.windows and self.windows[0].dummy:
            # Dummy is open; close it
            self.windows[0].OnClose(None)
            self.windows = []
            # First real window, put at top left
            x = 10
            y = 30
        else:
            x, y = self.windows[-1].GetPosition()
            x += 20
            y += 20

        logging.debug("about to open new window pos=%s size=%s minsize=%s" % (
                (x,y), size, minsize))
        window = PuzzleWindow(title=title, pos=(x, y), size=size,
                              minsize=minsize)
        logging.debug("window opened")
        self.windows.append(window)
        return window

    def open_puzzle(self, path, as_unsolved=False, reuse_window=False):
        """Open puzzle."""

        logging.debug("Request open puzzle: %s.", path)

        # Check if already open and, if so, show it
        for w in self.windows:
            if not w.dummy and w.puzzle.path == path:
                w.Raise()
                return

        puzzle = Puzzle()

        try:
            puzzle.load(path)

        except DiagramlessPuzzleFormatError:
            logging.error("Not valid puzzle format: %s", path)
            dlg = wx.MessageDialog(None,
                                   "Cannot use diagramless puzzles:\n%s." % path,
                                   "Format Error", wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return

        except PuzzleFormatError as e:
            logging.error("Not valid puzzle format: %s %s", path, e)
            dlg = wx.MessageDialog(None,
                                   "This is not a valid puzzle format file:\n %s" % path,
                                   "Format Error", wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return

        # Get reasonable size and min size for puzzle
        w = min(max(puzzle.width * 40 + 200, 500), 920)
        h = min(max(puzzle.height * 40 + 20, 320), 600)
        minw = puzzle.width * 22
        minh = puzzle.height * 22 + 25
        logging.debug("Opening size w=%s, h=%s", w, h)

        self.config.addRecentFile(path)
        logging.debug("recent files added")

        if reuse_window:
            window = self
        else:
            window = self.NewWindow(
                title=puzzle.filename_no_ext,
                size=(w, h),
                minsize=(minw, minh))
        logging.debug("new window created")
        window.setupPuzzle(puzzle, as_unsolved)
        logging.debug("Raising window")
        window.Raise()
        wx.GetApp().SetTopWindow(window)
        return window

    # --------------- Menu Events

    # ---- Open On-Disk Puzzles

    def OnOpen(self, event, as_unsolved=False):
        """Open file-based puzzle."""

        wildcard = "Across Lite Puzzle (*.puz)|*.puz"
        dlg = wx.FileDialog(self.GetTopWindow(),
                            message="Open Puzzle",
                            wildcard=wildcard,
                            style=wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.open_puzzle(path, as_unsolved)

        dlg.Destroy()

    def OnOpenUnsolved(self, event):
        """Open disk puzzle as unsolved."""

        return self.OnOpen(event, as_unsolved=True)

    def OnFileHistory(self, e):
        """Open recent file directly from menu."""

        fileNum = e.GetId() - wx.ID_FILE1
        path = self.config.filehistory.GetHistoryFile(fileNum)
        self.open_puzzle(path)

    # ---- Open from Web Puzzles

    def OnWebChooser(self, event):
        """Open web-based puzzle."""

        idx, startat = ShowWebOpenGUI()
        if idx is not None:
            path = WebOpenGUI(idx, startat)
            if path:
                self.open_puzzle(path)

    def OnOpenWeb(self, event, idx):
        """Open web-based puzzle."""

        path = WebOpenGUI(idx)
        if path:
            self.open_puzzle(path)

    # ---- Quit

    def OnQuit(self, event):
        """Quit application."""

        logging.debug("Quitting")

        self.config.persistWindows(
            [w.puzzle.path for w in self.windows if not w.dummy])

        for w in self.windows[:]:
            if not w.dummy:
                w.Raise()
                w.DoClose()

        if len(self.windows) == 1 and self.windows[0].dummy:
            self.windows[0].Destroy()

    # ---- About/Help/Preferences

    def OnAbout(self, event):
        """About application dialog box."""

        AboutBox()

    def OnHelp(self, event):
        """Show help."""

        ShowHelp()

    def OnBugReport(self, event):
        """Show bug report."""

        showBugReport(self.config)

    def OnPrefs(self, event):
        """Application preferences."""

        showPrefsDialog(self.config)

    # --------------- Other Events

    def BringWindowToFront(self):
        """Bring a window to the front."""

        logging.debug("app BringWindowToFront")
        # it's possible for this event to come when the frame is closed
        try:
            # We don't want to always raise the "top window", since this isn't
            # always the winow that was on the top of the stack when we were 
            # de-activated.
            # self.GetTopWindow().Raise()
            pass
        except Exception as e:
            logging.debug(e)
            pass

    def OnActivate(self, event):
        """Activate application."""

        # if this is an activate event, rather than something else, 
        # like iconize.
        logging.debug("app OnActivate")
        if event.GetActive():
            self.BringWindowToFront()
        event.Skip()

    # ---- Mac-specific events

    def MacOpenFile(self, filename):
        """Called for files droped on dock or opened via Finder context menu"""

        logging.info("MacOpenFile: %s", filename)
        if filename.endswith("run.py"):
            logging.debug("Skipping loading of this script.")
        else:
            self.open_puzzle(filename)

    def MacReopenApp(self):
        """Called when the doc icon is clicked, and ???"""

        logging.debug("app MacReopenApp")
        self.BringWindowToFront()

    def MacNewFile(self):
        """Create new file."""

        logging.debug("MacNewFile")

    def MacPrintFile(self, file_path):
        """Print."""

        logging.debug("MacPrint")


def clean_shutdown():
    logging.info("Clean shutdown")
    sys.stderr.flush()


def runApp():
    """Run the application."""

    xsocius.log.log_file = xsocius.log.setup_logging()
    atexit.register(clean_shutdown)
    app = XsociusApp().MainLoop()
