"""Puzzle window."""

import logging

import random
import wx
import wx.lib.buttons as buttons
from wx.lib.splitter import MultiSplitterWindow
from xsocius.utils import suggestSafeFilename
from xsocius.puzzle import FAST_UNLOCK
from xsocius.gui.window import BaseWindow
from xsocius.gui.board import Board
from xsocius.gui.oneacross import OpenOneAcross
from xsocius.gui.google import OpenGoogle
from xsocius.gui.clues import CluesPanel
from xsocius.gui.undo import UndoRedoMixin
from xsocius.gui.clipboard import ClipboardMixin
from xsocius.gui.share import SharingPanel, ShareWindowMixin
from xsocius.gui.timer import GameTimerMixin, TimerButton
from xsocius.gui.menu import PuzzleMenuBar
from xsocius.gui.printing import PrintMixin
from xsocius.gui.utils import get_icon, font_scale
from xsocius.gui.note import NoteWindow




# PuzzleWindow()  in here
# +--------------------------------------------------------------------------+
# | SharingPanel()   || wx.Panel() in here          || CluesPanel()          |
# | in gui/share.py  ||   .puzzle_panel             ||   in gui/clues.py     |
# |   .share_panel   ||                             ||   .clues_panel        |
# |                  || .clue_text                  ||                       |
# | +--------------+ ||                             || +-------------------+ |
# | | MsgList()    | || +----------------------+    || | AcrossCluesList() | |
# | |   .msg_list  | || | Board()              |    || |   .across_clues   | |
# | +--------------+ || |   in gui/board.py    |    || +-------------------+ |
# |                  || |   .board             |    ||                       |
# | +--------------+ || +----------------------+    || +-------------------+ |
# | | MsgEntry()   | ||                             || | DownCluesList()   | |
# | |   .msg_entry | || .puzzle_title        PB  TB || |   .down_clues     | |
# | +--------------+ || .puzzle_copyright           || +-------------------+ |
# |                  ||                             ||                       |
# +--------------------------------------------------------------------------+
#
# PB = .pen_button
# TB = .timer_button


class PenButton(buttons.GenBitmapToggleButton):
    """Pen/pencil button"""

    def __init__(self, parent):
        img = wx.Image(get_icon("pencil-icon.png"))
        bmp = img.ConvertToBitmap()
        buttons.GenBitmapToggleButton.__init__(self, parent, wx.ID_ANY, bmp)
        self.Bind(wx.EVT_BUTTON, self.OnToggle)
        self.Bind(wx.EVT_SET_FOCUS, self.IHaveFocus)
        self.puzw = self.GetTopLevelParent()

    def IHaveFocus(self, event):
        """Pen Button has focus; move it."""

        logging.debug("Pen button moving focus back to board")
        self.puzw.board.SetFocus()

    def OnToggle(self, event):
        """Toggle pen button."""

        logging.debug("on pen/pencil toggle")
        self.puzw.pencil = not self.puzw.pencil
        tool = "Pen" if self.puzw.pencil else "Pencil"
        self.puzw.GetMenuBar() \
            .FindItemById(self.puzw.ID_TOGGLE_PEN).SetText("Use %s\tCtrl-E" % tool)


class PuzzleWindow(BaseWindow,
                   UndoRedoMixin,
                   ClipboardMixin,
                   GameTimerMixin,
                   ShareWindowMixin,
                   PrintMixin):
    """A window with a puzzle in it."""

    no_autowin = False
    pencil = False
    fullscreen = False

    def __init__(self, title, pos=(-1, -1), size=(700, 500), minsize=(700, 500)):
        """Setup window and sub-panels."""

        logging.debug("in PuzzleWindow __init__")
        BaseWindow.__init__(self, title, pos, size=size)
        logging.debug("done base")
        UndoRedoMixin.__init__(self)
        ClipboardMixin.__init__(self)
        ShareWindowMixin.__init__(self)
        PrintMixin.__init__(self)
        logging.debug("done mixins")

        self.SetMenuBar(PuzzleMenuBar(self))
        logging.debug("done menubar")
        # self.ShowFullScreen(True)

        self.splitter = MultiSplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        logging.debug("made splitter")
        self.share_panel = SharingPanel(self.splitter)
        self.puzzle_panel = wx.Panel(self.splitter, wx.ID_ANY)
        logging.debug("done panels")

        if wx.Platform == "__WXMAC__":
            # This seems a little self-evident, but it needed to workaround
            # display bug in OSX Mountain Lion
            self.puzzle_panel.SetBackgroundColour(self.GetBackgroundColour())
        elif wx.Platform == "__WXGTK__":
            self.puzzle_panel.SetBackgroundColour("White")

        self.clues_panel = CluesPanel(self.splitter)

        self.splitter.AppendWindow(self.share_panel, 280)
        self.splitter.AppendWindow(self.puzzle_panel, 250)
        self.splitter.DetachWindow(self.share_panel)
        self.share_panel.Hide()
        logging.debug("done splitter")

        minw, minh = minsize
        if wx.GetApp().config.show_clues:
            self.splitter.AppendWindow(self.clues_panel, 180)
            minw += 180
        else:
            self.clues_panel.Hide()
        self.SetMinSize((minw, minh))

        # Events for general window stuff

        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGING, self.OnChangingSplitter)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.splitter.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)

        # These get instantiated in setupPuzzle

        self.cluetext = self.puzzletitle = self.puzzlecopyright = self.pen_button \
            = self.timer_button = None

    def size_clue_text(self):
        """Set size of clue text, partially based on window size."""

        size = font_scale(20)

        scale = max(self.puzzle_panel.GetSize()[0] / 1000.0, 0.6)
        logging.debug("clue_text size scale = %s", scale)

        self.cluetext.SetFont(wx.Font(int(size * scale),
                                      wx.FONTFAMILY_DEFAULT,
                                      wx.FONTSTYLE_NORMAL,
                                      wx.FONTWEIGHT_BOLD))

    def setupPuzzle(self, puzzle, as_unsolved=False):
        """Setup puzzle sub-panes, board, and clues.
        
        This sets up all the appearance/binding/wx stuff; for logical things having to do with
        the beginning of the play of the puzzle, put that is startPuzzle (ie, if you wanted to
        note the time when a puzzle-solving session began). startPuzzle is called if we choose
        to restart a puzzle, this is called only open opening of a puzzle in the GUI.
        """

        # Panel where board & labels will go

        self.puzzle_panel.puzzle = self.puzzle = puzzle
        puzzle.gui = self

        # Current clue text appears at top of puzzle in bold
        # (actual text is dynamically filled in)

        self.cluetext = wx.StaticText(self.puzzle_panel)
        self.cluetext.SetForegroundColour("#444444")

        # Puzzle title appear below grid

        if puzzle.author:
            title = "{0.title} - {0.author}".format(puzzle)
        else:
            title = puzzle.title
        self.puzzletitle = wx.StaticText(self.puzzle_panel, label=title)
        self.puzzletitle.SetFont(wx.Font(font_scale(11),
                                         wx.FONTFAMILY_DEFAULT,
                                         wx.FONTSTYLE_NORMAL,
                                         wx.FONTWEIGHT_NORMAL))
        self.puzzletitle.SetForegroundColour("#222222")

        # Puzzle copyright is below that any tiny

        self.puzzlecopyright = wx.StaticText(self.puzzle_panel, label=puzzle.copyright)
        self.puzzlecopyright.SetFont(wx.Font(font_scale(9),
                                             wx.FONTFAMILY_DEFAULT,
                                             wx.FONTSTYLE_NORMAL,
                                             wx.FONTWEIGHT_NORMAL))
        self.puzzlecopyright.SetForegroundColour("#222222")

        # Add pen button

        self.pen_button = PenButton(self.puzzle_panel)

        # Add timer

        self.timer_button = TimerButton(self.puzzle_panel)

        # Add board, and labels to main panel

        self.board = Board(self.puzzle_panel)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.cluetext, 0, wx.TOP | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        sizer.Add(self.board, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        self.bottomsizer = bottomsizer = wx.BoxSizer(wx.HORIZONTAL)
        blsizer = wx.BoxSizer(wx.VERTICAL)
        blsizer.Add(self.puzzletitle)
        blsizer.Add(self.puzzlecopyright)
        bottomsizer.Add(blsizer, 1, wx.EXPAND)
        bottomsizer.Add(self.pen_button, 0, wx.ALIGN_RIGHT)
        bottomsizer.Add(self.timer_button, 0, wx.ALIGN_RIGHT)

        sizer.Add(bottomsizer, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        self.puzzle_panel.SetSizer(sizer)

        # Fill clues into lists

        clues = self.puzzle.clues[1:]
        self.across_clues.populate([(c.num, c.across) for c in clues if c.across])
        self.down_clues.populate([(c.num, c.down) for c in clues if c.down])

        # Show puzzle and get started

        if as_unsolved:
            self.restartPuzzle()
        else:
            self.startPuzzle()

        sizer.Fit(self.puzzle_panel)

        # Puzzle-related events

        self.Bind(wx.EVT_IDLE, self.OnIdle)
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateSave)
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateSpecialAnswer)
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateCluesOptions)
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateGoogle)

        self.Show()
        self.board.SetFocus()
        self.board.updateClueHighlight()
        self.tournamentSettings()
        config = wx.GetApp().config
        self.puzzle.grey_filled_clues = config.grey_filled_clues
        self.puzzle.on_any_change(skip_check_finished=True)

        self.need_show_locked = self.puzzle.pfile.is_solution_locked()
        self.size_clue_text()

        # Add Balloon help to clue text
        self.cluetext.Bind(wx.EVT_ENTER_WINDOW, self.hover_clue)
        self.cluetext.Bind(wx.EVT_LEAVE_WINDOW, self.end_hover_clue)

    def on_any_change(self):
        """Called by underlying puzzle when anything changes."""

        if wx.GetApp().config.flash_correct:
            self.flash_correct()

    def flash_correct(self):
        """If our change makes current word correct, flash it."""

        # True if word is correct; False if completed but wrong, None if not completed
        correct = self.puzzle.is_curr_word_correct()

        if correct is True or correct is False:
            for cell in self.puzzle.curr_word():
                cell.flash_correct = correct
            self.board.DrawNow()

            wx.CallLater(100, self.flash_clear)

    def flash_clear(self):
        """Clear flash."""

        for row in self.puzzle.grid:
            for cell in row:
                cell.flash_correct = None
        self.board.DrawNow()

    def hover_clue(self, event):
        """Show clue when you hover over clue text above grid.
        
        This is useful when the clue is too large to be completely readable in that space.
        """

        logging.debug("hover on clue")
        self.hoverclue = hc = wx.StaticText(self.puzzle_panel,
                                            wx.ID_ANY,
                                            self.cluetext.GetLabel(),
                                            pos=(10, 10),
                                            style=wx.BORDER_SIMPLE)
        hc.SetBackgroundColour("#FFFFEE")
        hc.SetFont(wx.Font(font_scale(14),
                           wx.FONTFAMILY_DEFAULT,
                           wx.NORMAL,
                           wx.BOLD))

        hc.Wrap(self.puzzle_panel.GetSize()[0] - 10)

    def end_hover_clue(self, event):
        """Hide clue when you leave hover over clue text above grid."""

        logging.debug("hover off clue")
        try:
            self.hoverclue.Destroy()
        except Exception:
            pass

    def setupScrambled(self):
        """If puzzle is scrambled, hide check/reveal links."""

        for i in [self.ID_CHECK_LETTER,
                  self.ID_CHECK_WORD,
                  self.ID_CHECK_PUZZLE,
                  self.ID_REVEAL_LETTER,
                  self.ID_REVEAL_WORD,
                  self.ID_REVEAL_PUZZLE,
                  self.ID_REVEAL_WRONG,
                  self.ID_LOCK,
                  ]:
            self.GetMenuBar().FindItemById(i).Enable(False)

        dlg = wx.MessageDialog(
            None,
            "This puzzle has a scrambled solution, so it is not possible to use the functions "
            "for checking or revealing correct letters.\n\n"
            "You can unlock the solution with the 'Unlock Puzzle' option in the Puzzle menu.",
            "Scrambled Puzzle",
            style=wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

        if not wx.GetApp().config.no_unlock:
            self.GetMenuBar().FindItemById(self.ID_UNLOCK).Enable(True)
        self.need_show_locked = False

    def startPuzzle(self):
        """Called at start (or restart) of puzzle.
        
        Technical stuff having to do with the GUI setup of a puzzle should be put in
        setupPuzzle; that is not called when we restart a puzzle.
        """

        self.need_show_note = False
        if self.puzzle.note:
            logging.debug("Has note: =%s=", self.puzzle.note)
            self.GetMenuBar().Enable(self.ID_SHOW_NOTE, True)  # test
            config = wx.GetApp().config
            if config.note_on_open:
                self.need_show_note = True
        else:
            self.GetMenuBar().Enable(self.ID_SHOW_NOTE, False)  # test

        self.puzzle.initPuzzleCursor()

        GameTimerMixin.__init__(self, self.puzzle.timer_start, not self.puzzle.timer_start_paused)

    def restartPuzzle(self):
        """Restart puzzle.

        Called on open-as-unsolved, by using clear in menu,
        or by partner choosing clear.
        """

        for x in self.puzzle.grid:
            for y in x:
                if not y.black:
                    y.reset()

        self.startPuzzle()
        self.board.DrawNow()
        self.puzzle.add_undo()

    def tournamentSettings(self):
        """Set tournament settings."""

        config = wx.GetApp().config
        find = self.GetMenuBar().FindItemById

        for i in [self.ID_CHECK_LETTER,
                  self.ID_CHECK_WORD,
                  self.ID_CHECK_PUZZLE,
                  self.ID_REVEAL_LETTER,
                  self.ID_REVEAL_WORD,
                  self.ID_REVEAL_PUZZLE,
                  self.ID_REVEAL_WRONG,
                  ]:
            find(i).Enable(not config.no_cheats)

        find(self.ID_ONEACROSS).Enable(not config.no_oneacross)

        if config.no_unlock:
            find(self.ID_UNLOCK).Enable(False)
        else:
            find(self.ID_UNLOCK).Enable(self.puzzle.pfile.is_solution_locked())

        self.no_autowin = config.no_autowin

        self.timer_button.Enable(not config.no_timerpause)
        find(self.ID_TIMER_TOGGLE).Enable(not config.no_timerpause)
        find(self.ID_TIMER_CLEAR).Enable(not config.no_timerpause)
        if config.no_timerpause:
            self.start_timer()

    def showNote(self):
        """Show puzzle note."""

        # dlg = wx.lib.dialogs.ScrolledMessageDialog(None, self.puzzle.note,
        #                                        "Puzzle Note",
        #                                        size=(500, 800))
        # dlg.ShowModal()
        # dlg.Destroy()

        note = NoteWindow(self.puzzle.note)
        self.need_show_note = False

    def UpdatePrefs(self):
        """Prefs were updated; make any needed changes."""

        self.board.setupColors()
        self.board.setupSkipLetters()
        self.tournamentSettings()
        self.board.DrawNow()

        config = wx.GetApp().config
        self.puzzle.grey_filled_clues = config.grey_filled_clues

        # If we now no longer want to see clues changed when filled in, reset this everywhere--
        # then we'll see this switch back to all black

        if not self.puzzle.grey_filled_clues:

            append = self.puzzle.clues_completed_queue.append

            for clue in self.puzzle.clues[1:]:
                if clue.across_filled:
                    append(('across', clue.across_idx, False))
                if clue.down_filled:
                    append(('down', clue.down_idx, False))

        # If we now do want to see greyed-out clues, we need
        # manually ask for this everywhere.

        else:
            self.puzzle.check_clue_fill_change(force=True)

    # ---------------- MENU EVENTS
    #
    # Menu items specific to a puzzle are defined here; ones that are not
    # (eg open puzzle, quit, etc) are in gui/app.py.


    # --------- File Menu

    def DoClose(self):
        """Check if we're dirty and, if so, prompt to save."""

        if self.puzzle.dirty:
            dlg = wx.MessageDialog(self,
                                   ('The document "%s" has unsaved changes.\n\n'
                                    'Would you like to save your changes before closing?\n') %
                                   self.puzzle.filename,
                                   'Save Changes?',
                                   wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_CANCEL:
                return False
            elif result == wx.ID_YES:
                self._save_puzzle()

        # Remove this window's menu from updating recent files
        wx.GetApp().config.filehistory.RemoveMenu(self.RecentMenu)

        # Close & destroy window
        self.stop_timer()
        if self.xmpp:
            self.XMPPDisconnect()
        self.Destroy()
        wx.GetApp().windows.remove(self)

    def OnClose(self, event):
        """Close puzzle."""

        logging.debug("On close")
        self.DoClose()

        # If no windows open, show dummy
        if not wx.GetApp().windows:
            wx.GetApp().OpenDummy()

        logging.debug("On close done")

    def _save_puzzle(self, path=None):
        """Save puzzle, showing errors.
        
        Called by DoClose, OnQuit, OnSave, and OnSaveAs.
        """

        try:
            self.puzzle.save_puzzle(path)
        except IOError as e:
            dlg = wx.MessageDialog(None, "Fail saved: %s" % e,
                                   "Save Error", wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return

    def OnSave(self, event):
        """Save puzzle."""

        self._save_puzzle()

    def OnSaveAs(self, event):
        """Save-as puzzle."""

        wildcard = "Across Lite Puzzle (*.puz)|*.puz"

        fname = suggestSafeFilename(self.puzzle.dirname, self.puzzle.filename)
        dlg = wx.FileDialog(
            self,
            message="Save puzzle as ...",
            defaultDir=self.puzzle.dirname,
            defaultFile=fname,
            wildcard=wildcard,
            style=wx.SAVE
        )
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self._save_puzzle(path=path)

        dlg.Destroy()

    def OnRevert(self, event):
        """Revert to saved version of puzzle."""

        self.puzzle.revert_puzzle()
        self.board.DrawNow()

    # --------- Edit Menu



    def OnStartOver(self, event):
        """Start puzzle over.
        
        Often called by 
        """

        dlg = wx.MessageDialog(self,
                               "Are you sure you want to clear the entire grid?",
                               "Clear Grid?",
                               wx.OK | wx.CANCEL)
        result = dlg.ShowModal()
        dlg.Destroy()
        if result == wx.ID_CANCEL:
            return

        self.restartPuzzle()

        if self.xmpp is not None:
            self.xmpp.send_clear([("*", "*")])

    def OnSpecialAnswer(self, event):
        """Enter special answer in cell."""

        self.board.SpecialAnswer()

    def OnTogglePen(self, event):
        """Toggle pencil/pen"""

        self.pencil = not self.pencil
        tool = "Pen" if self.pencil else "Pencil"
        self.GetMenuBar().FindItemById(self.ID_TOGGLE_PEN).SetText("Use %s\tCtrl-E" % tool)
        self.pen_button.SetValue(self.pencil)

    # --------- Puzzle Menu


    def OnShowNote(self, event):
        """Show puzzle note."""

        self.showNote()

    def OnCheckLetter(self, event):
        """Check letter under cursor."""

        if self.puzzle.check_letter():
            self.board.DrawNow()

    def OnCheckWord(self, event):
        """Check current word."""

        if self.puzzle.check_word():
            self.board.DrawNow()

    def OnCheckPuzzle(self, event):
        """Check entire puzzle."""

        if self.puzzle.check_puzzle():
            self.board.DrawNow()

    def OnRevealLetter(self, event):
        """Reveal current letter."""

        if self.puzzle.reveal_letter():
            self.board.DrawNow()

    def OnRevealWord(self, event):
        """Reveal curent word."""

        if self.puzzle.reveal_word():
            self.board.DrawNow()

    def OnRevealPuzzle(self, event):
        """Reveal entire puzzle."""

        if self.puzzle.reveal_puzzle():
            self.board.DrawNow()

    def OnRevealWrong(self, event):
        """Reveal incorrect letters."""

        if self.puzzle.reveal_incorrect():
            self.board.DrawNow()

    def OnUnlock(self, event):
        """Unlock puzzle."""

        # This  might be able to use the speed C-based unlocker or the Python one. We could treat
        # them the same but the C one is so much faster that it doesn't make sense to show all the
        # dialog boxes.

        if FAST_UNLOCK:
            key = self.puzzle.break_encryption()

        else:

            dlg = wx.MessageDialog(self,
                                   "Depending on the speed of your computer, unlocking a"
                                   " puzzle can take several seconds. Once unlocked, you"
                                   " can use the check and reveal features of the puzzle."
                                   "\n\nUnlock puzzle?",
                                   "Unlock Puzzle?", wx.OK | wx.CANCEL)
            result = dlg.ShowModal()
            dlg.Destroy()

            if result != wx.ID_OK:
                return

            dlg = wx.ProgressDialog(
                "Unlocking",
                "Unlocking puzzle. This may take a moment.",
                maximum=8999,  # num of possibilities
                parent=self,
                style=(wx.PD_APP_MODAL | wx.PD_CAN_ABORT
                       | wx.PD_ELAPSED_TIME | wx.PD_AUTO_HIDE))

            # Key is from 1000-9999

            keep_going = True
            key = 1000
            unlocked = False

            unlock_solution = self.puzzle.pfile.unlock_solution

            while keep_going and key < 10000:
                if unlock_solution(key):
                    unlocked = True
                    break
                if key % 25 == 0:
                    # Updating dlg for every key attempt slows down loop;
                    # Do once every 25 times and it's still nicely responsive
                    # to canceling and updating time.
                    (keep_going, skip) = dlg.Update(key - 1000)
                key += 1

            dlg.Destroy()

            # busy = PBI.PyBusyInfo("Decrypting; please wait...")
            # wx.Yield()

            # del busy

        if not key:
            wx.MessageBox("Puzzle could not be unlocked.")
            return

        # Reload puzzle
        self.board.DrawNow()

        # Mark as dirty so Save is enabled
        self.puzzle.dirty = True

        wx.MessageBox("Puzzle successfully unlocked. Key was: %s" % key)
        if not wx.GetApp().config.no_cheats:
            for i in [self.ID_CHECK_LETTER,
                      self.ID_CHECK_WORD,
                      self.ID_CHECK_PUZZLE,
                      self.ID_REVEAL_LETTER,
                      self.ID_REVEAL_WORD,
                      self.ID_REVEAL_PUZZLE,
                      self.ID_REVEAL_WRONG,
                      ]:
                self.GetMenuBar().FindItemById(i).Enable(True)
        self.GetMenuBar().FindItemById(self.ID_LOCK).Enable(True)
        self.GetMenuBar().FindItemById(self.ID_UNLOCK).Enable(False)

    def OnLock(self, event):
        """Lock puzzle."""

        dlg = wx.TextEntryDialog(self,
                                 "Enter a numeric code between 1000 and 9999 to lock puzzle.",
                                 "Lock Puzzle")
        dlg.SetValue(str(random.randint(1000, 9999)))

        fail = False
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            try:
                key = int(dlg.GetValue())
            except ValueError:
                fail = True
            else:
                if key < 1000 or key > 9999 or len(dlg.GetValue()) != 4:
                    fail = True

            if fail:
                wx.MessageBox("Invalid key. Lock operation failed.")
                return

            self.puzzle.pfile.lock_solution(key)

            # Reload puzzle
            self.puzzle.updateAnswers()
            self.board.DrawNow()

            # Mark as dirty so Save is enabled
            self.puzzle.dirty = True

            wx.MessageBox("Puzzle successfully locked.")
            for i in [self.ID_CHECK_LETTER,
                      self.ID_CHECK_WORD,
                      self.ID_CHECK_PUZZLE,
                      self.ID_REVEAL_LETTER,
                      self.ID_REVEAL_WORD,
                      self.ID_REVEAL_PUZZLE,
                      self.ID_REVEAL_WRONG,
                      self.ID_LOCK,
                      ]:
                self.GetMenuBar().FindItemById(i).Enable(False)
            if not wx.GetApp().config.no_unlock:
                self.GetMenuBar().FindItemById(self.ID_UNLOCK).Enable(True)

    def _cluesFontChange(self, delta):
        """Change font size of clue list."""

        for cl in [self.across_clues, self.down_clues]:
            cl.font_size += delta
            cl.changeFontSize()

    def OnCluesFontBigger(self, event):
        """Increase font size of clue list."""

        self._cluesFontChange(+1)

    def OnCluesFontSmaller(self, event):
        """Decrease font size of clue list."""

        self._cluesFontChange(-1)

    def OnShowClues(self, event):
        """Toggle visibility of clue lists."""

        minw = self.puzzle.width * 22
        minh = self.puzzle.height * 22 + 25
        w, h = self.Size

        if event.IsChecked():
            self.splitter.InsertWindow(2, self.clues_panel, 200)
            minw += 150
            self.SetSize((w + 250, h))
        else:
            self.splitter.DetachWindow(self.clues_panel)
            self.clues_panel.Hide()
            self.SetSize((max(w - 250, minw), h))
        logging.debug("Min size w=%s, h=%s", minw, minh)
        self.SetMinSize((minw, minh))
        self.OnSize(None)

    def OnOneAcross(self, event):
        """Lookup current clue in oneacross.com."""

        clue = self.puzzle.curr_clue()
        word = self.puzzle.curr_word_text()
        # Sometimes, using key shortcut keeps Puzzle highlit
        # Let's make sure this happens out-of-band.
        wx.CallAfter(OpenOneAcross, clue, word)

    def OnGoogle(self, event):
        """Lookup current clue in google.com."""

        clue = self.puzzle.curr_clue()
        word = self.puzzle.curr_word_text()
        # Sometimes, using key shortcut keeps Puzzle highlit
        # Let's make sure this happens out-of-band.
        wx.CallAfter(OpenGoogle, clue, word)

    def OnFullScreen(self, event):
        """Switch to full-screen."""

        logging.debug("fullscreen")
        self.fullscreen = not self.fullscreen
        self.bottomsizer.Clear()
        self.ShowFullScreen(self.fullscreen)

    # ---------------- OTHER EVENTS

    def OnIdle(self, event):
        """Idle activities.
        
        Things go here if:

        - they need to happen after setup once all the rendering is done.

        - they need to react to changes in the underlying puzzle that don't flow through the GUI
          code (like seeing if the puzzle is dirty or solved)
        """

        # We don't want to show these notes until the entire screen has been rendered and sized
        # and this window is brought to the front, so we can't put in the setupPuzzle-style places.
        # It will only be done once.

        if self.IsActive() and self.need_show_note:
            self.showNote()

        if self.IsActive() and self.need_show_locked:
            self.setupScrambled()

        # Check if puzzle-is-correct flag is set and, if so, announce congratulations.

        if self.puzzle.puzzle_correct_flag and not self.no_autowin:
            self.stop_timer()
            self.puzzle.puzzle_correct_flag = False
            dlg = wx.MessageDialog(self,
                                   'Good work!',
                                   'Puzzle Finished',
                                   wx.OK | wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()

        for direction, idx, filled in self.puzzle.clues_completed_queue:
            if direction == "across":
                self.across_clues.update_filled(idx, filled)
            else:
                self.down_clues.update_filled(idx, filled)
        self.puzzle.clues_completed_queue = []

        # On OSX, this puts a black dot in the close button when puzzle
        # is dirty (a common OSX UI thing to do). On other systems, this
        # is a no-op.

        self.OSXSetModified(self.puzzle.dirty)

    def OnUpdateGoogle(self, event):
        """Update Google menu options to reflect state of system.
        
        In order to use the Google lookup, the word you're on needs to be completed.
        """

        event_id = event.GetId()
        if event_id == self.ID_GOOGLE:
            event.Enable(self.puzzle.curr_word_complete())
        else:
            event.Skip()

    def OnUpdateSave(self, event):
        """Update save menu options to reflect state of system."""

        event_id = event.GetId()
        if event_id == self.ID_SAVE:
            event.Enable(self.puzzle.dirty)
        else:
            event.Skip()

    def OnUpdateSpecialAnswer(self, event):
        """Only allow special answers in rebus squares."""

        event_id = event.GetId()
        if event_id == self.ID_ENTER_REBUS:
            event.Enable(bool(self.puzzle.curr_cell.rebus_answer))
        else:
            event.Skip()

    def OnUpdateCluesOptions(self, event):
        """Only allow font +/- if clues visible."""

        event_id = event.GetId()
        if event_id == self.ID_CLUES_BIGGER or event_id == self.ID_CLUES_SMALLER:
            event.Enable(self.clues_panel.Shown)
        else:
            event.Skip()

    def OnMouse(self, evt):
        """Mouse used in window."""

        # THIS IS A DREADFUL HACK.
        #
        # Normally, if user resizes a splitter, it add/takes away space from the edge window
        # (ie, if user resizes splitter between sharing + board, the clues window changes width
        # to match). We want the "nearer neighbor" to change (the board window). wxWindows handles
        # this automatically if the shift key is held down during resize.
        #
        # There does not appear to be a way to get this behavior except by tricking it into
        # thinking the shift key is held down during all mouse movement. So, set shift key down
        # and then delegate to the underlying wx call for mousing on the splitter.

        logging.debug("on mouse")

        if hasattr(evt, 'SetShiftDown'):
            # Not present in wx2.8
            evt.SetShiftDown(True)
        self.splitter._OnMouse(evt)

    def OnChangingSplitter(self, evt):
        """Changing splitters between windows."""

        logging.debug("on changing splitter")
        if evt.GetSashPosition() < 180:
            # Minimum size for each splitter
            evt.Veto()
        self.size_clue_text()

    def OnSize(self, evt=None):
        """Resizing window."""

        # Keep proportions of splits

        logging.debug("On size")
        if evt:
            w = evt.GetSize()[0]
        else:
            w = self.GetSize()[0]

        if self.share_panel.IsShown() and self.clues_panel.IsShown():
            self.splitter.SetSashPosition(0, 180)
            self.splitter.SetSashPosition(1, ((w - 180) * .65))
        elif self.share_panel.IsShown():
            self.splitter.SetSashPosition(0, 180)
        elif self.clues_panel.IsShown():
            self.splitter.SetSashPosition(0, w * .55)
        else:
            # self.splitter.SetSashPosition(0, w)
            pass

        self.splitter.SizeWindows()
        if evt:
            evt.Skip()

        self.size_clue_text()
