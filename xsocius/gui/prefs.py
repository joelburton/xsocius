"""GUI prefs panel."""

import wx
import wx.lib.colourselect as csel
import wx.lib.agw.pybusyinfo as PBI

from xsocius.puzzle import Clue, Cell

from xsocius.utils import VERSION
from xsocius.gui.web import WebOpenList
from xsocius.gui.share import addLogOnDialogOptions
from xsocius.gui.utils import makeHeading, makeHint, makeText
from xsocius.gui.utils import get_icon, font_scale
from xsocius.gui.board import PresentationBoardMixin
from xsocius.gui.upgrade import newest_version_info, prompt_update_version

INT_BROWSER = "Use internal browser"
EXT_BROWSER = "Use default external browser"

URL_HELP = """Use percent-codes for template URL: %d = day, %m = month, 
%y = 2-digit year, %Y = 4-digit year, %b = short month name."""


def wx2hex_color(color):
    """Turn wx color into #AABBCC"""

    return "#%02x%02x%02x" % (color.red, color.green, color.blue)


def h2wx_color(color):
    """Turn hex color in wx.Colour()"""

    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:], 16)
    return wx.Colour(red, green, blue)


def color_select(self, value):
    """Make a colour select widget."""

    return csel.ColourSelect(self, wx.ID_ANY, "", 
            h2wx_color(value), size=(25,25))


def _checkbox(self, text, default):
    """Make a checkbox widget."""

    cb = wx.CheckBox(self, wx.ID_ANY, text)
    cb.SetValue(default)
    return cb


class FakePuzzle(object):
    """Fake puzzle to attach grid, clues to.
    
    Used so we can show an example grid in the appearances preference
    pane.
    """

    width = None
    height = None
    grid = None
    clues = None


# ---
#
# Each preference pane is represented by a class that is mostly autonomous
# in reading and setting the underlying preferences on it. 
#
# All of the panes are tied together in the dialog class at the end of this
# file. This manages updating the app and windows with the configs that the
# individual panes made, along with the overall dialog layout.


    
class AppearancePrefs(wx.Panel, PresentationBoardMixin):
    """Preferences for graphic/text flags and display of clue lists."""

    # Mark this is a "demo" board, so the display doesn't try to show 
    # current cell, etc.
    demo = True

    def __init__(self, parent, config):
        wx.Panel.__init__(self, parent)

        self.config = config

        flag_label = makeHeading(self, "Puzzle Flags")
        self.flag_graphic_cbox = _checkbox(self, 
                "Show by graphic color", config.flag_graphic)
        self.flag_letter_cbox = _checkbox(self, 
                "Show by text color", config.flag_letter)

        # Window where we'll show effect of flags/colors
        self.puzzle_win = wx.Window(self, wx.ID_ANY, size=(200, 50))
        self.puzzle_win.SetBackgroundColour("Red")

        self.letter_error_label =   makeText(self, "Incorrect letter color:")
        self.letter_checked_label = makeText(self, "Checked letter color:")
        self.letter_cheat_label =   makeText(self, "Revealed letter color:")
        self.letter_error =   color_select(self, config.letter_error_color)
        self.letter_checked = color_select(self, config.letter_checked_color)
        self.letter_cheat =   color_select(self, config.letter_cheat_color)

        self.graphic_error_label =   makeText(self, "Incorrect symbol color:")
        self.graphic_checked_label = makeText(self, "Checked symbol color:")
        self.graphic_cheat_label =   makeText(self, "Revealed symbol color:")
        self.graphic_error =   color_select(self, config.graphic_error_color)
        self.graphic_checked = color_select(self, config.graphic_checked_color)
        self.graphic_cheat =   color_select(self, config.graphic_cheat_color)

        self.reset = wx.Button(self, wx.ID_ANY, "Reset to Defaults")

        show_clues_label = makeHeading(self, "Clue List")
        self.show_clues = _checkbox(self, "Opens automatically with puzzle", 
                config.show_clues)
        self.grey_filled_clues = _checkbox(self, 
                "Lighten clues once filled in?",
                config.grey_filled_clues)

        sizer = wx.FlexGridSizer(rows=3, cols=5, vgap=0, hgap=5)
        sizer.AddMany( [ (self.letter_checked_label),
                         (self.letter_checked),
                         (0, 0),
                         (self.graphic_checked_label),
                         (self.graphic_checked),

                         (self.letter_error_label),
                         (self.letter_error),
                         (0, 0),
                         (self.graphic_error_label),
                         (self.graphic_error),

                         (self.letter_cheat_label),
                         (self.letter_cheat),
                         (0, 0),
                         (self.graphic_cheat_label),
                         (self.graphic_cheat),
                       ] )
        osizer = wx.BoxSizer(wx.VERTICAL)
        osizer.AddMany( [ 
                         (flag_label, 0, wx.LEFT|wx.TOP|wx.BOTTOM, 10),
                         (self.puzzle_win, 0, wx.LEFT, 30),
                         (15, 15),
                         (self.flag_letter_cbox, 0, wx.LEFT|wx.RIGHT, 30),
                         (self.flag_graphic_cbox, 0, wx.LEFT|wx.RIGHT, 30),
                         (15, 15),
                         (sizer, 0, wx.LEFT, 30),
                         (10, 10),
                         (self.reset, 0, wx.LEFT, 30),
                         (10, 10),
                         (show_clues_label, 0, wx.LEFT|wx.TOP|wx.BOTTOM, 10),
                         (self.show_clues, 0, wx.LEFT|wx.RIGHT,30),
                         (self.grey_filled_clues, 0, wx.LEFT|wx.RIGHT,30),
                         (20, 20),
                         ])
        self.SetSizer(osizer)

        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdate)
        self.Bind(wx.EVT_CHECKBOX, self.updateBoard, self.flag_graphic_cbox)
        self.Bind(wx.EVT_CHECKBOX, self.updateBoard, self.flag_letter_cbox)
        self.Bind(csel.EVT_COLOURSELECT, self.updateBoard)
        self.Bind(wx.EVT_BUTTON, self.OnReset, self.reset)
        self.puzzle_win.Bind(wx.EVT_PAINT, self.OnPaint)

        self.makeFakePuzzle()
        self.updateBoard(None)


    def makeFakePuzzle(self):
        """Construct mini fake puzzle for demo display of appearance."""

        clue1 = Clue(num=1)
        clue2 = Clue(num=2)
        clue3 = Clue(num=3)
        clue4 = Clue(num=4)

        cell1 = Cell(0, 0, down=clue1, response="D", 
                checked=False, revealed=False)
        cell2 = Cell(1, 0, down=clue2, response="E", 
                checked=True, revealed=False, answer="E")
        cell3 = Cell(2, 0, down=clue3, response="M", 
                checked=True, revealed=False, answer="Z")
        cell4 = Cell(3, 0, down=clue4, response="O", 
                checked=False, revealed=True)

        clue1.cell = cell1
        clue2.cell = cell2
        clue3.cell = cell3
        clue4.cell = cell4
 
        self.puzzle = FakePuzzle()
        self.puzzle.grid = [ [cell1], [cell2], [cell3], [cell4] ]
        self.puzzle.clues = [ None, clue1, clue2, clue3, clue4 ]
        self.puzzle.height = 1
        self.puzzle.width = 4
        
        self.rects = [[wx.Rect() for y in range(1)] for x in range(4)]


    def setupColors(self):
        """Setup colors for drawing."""

        # Copied from board, so we don't use the saved colors, but the
        # ones here.

        self.letter_normal_color =   "Black"
        self.letter_error_color =    self.letter_error.GetValue()
        self.letter_checked_color =  self.letter_checked.GetValue()
        self.letter_cheat_color =    self.letter_cheat.GetValue()
        self.graphic_error_color =   self.graphic_error.GetValue()
        self.graphic_checked_color = self.graphic_checked.GetValue()
        self.graphic_cheat_color =   self.graphic_cheat.GetValue()

        self.graphic_error_pen =     wx.Pen(self.graphic_error_color)
        self.graphic_checked_pen =   wx.Pen(self.graphic_checked_color)
        self.graphic_cheat_pen =     wx.Pen(self.graphic_cheat_color)
        self.graphic_error_brush =   wx.Brush(self.graphic_error_color)
        self.graphic_checked_brush = wx.Brush(self.graphic_checked_color)
        self.graphic_cheat_brush =   wx.Brush(self.graphic_cheat_color)
        self.circle_pen =            wx.Pen("#777777")
        self.circle_brush =          wx.Brush("#DDDDDD")

        self.flag_graphic = self.flag_graphic_cbox.GetValue()
        self.flag_letter = self.flag_letter_cbox.GetValue()

        self.color_cell_pen = wx.Pen("Black")               

        self.cell_normal_brush =    wx.Brush("White")


    def OnUpdate(self, event):
        """Only allow choosing colors if that type of flag is enabled."""

        item = event.GetEventObject()
        if item in (self.letter_error, 
                    self.letter_checked, 
                    self.letter_cheat,
                    self.letter_error_label, 
                    self.letter_checked_label, 
                    self.letter_cheat_label):
            event.Enable(self.flag_letter_cbox.IsChecked())

        elif item in (self.graphic_error, 
                      self.graphic_checked, 
                      self.graphic_cheat,
                      self.graphic_error_label, 
                      self.graphic_checked_label, 
                      self.graphic_cheat_label):
            event.Enable(self.flag_graphic_cbox.IsChecked())
        else:
            event.Skip()


    def updateBoard(self, event):
        """Draw board."""

        self.setupColors()
        w, h = (200, 50)
        self.buffer = wx.Bitmap(w, h)
        self.PrepareDrawSizing(w, h)
        dc = wx.MemoryDC()
        dc.SelectObject(self.buffer)
        self.DrawBoard(dc)
        del dc
        self.puzzle_win.Refresh()
        self.puzzle_win.Update()
        self.Refresh()
        self.Update()


    def OnPaint(self, event):
        """Paint the board."""

        wx.BufferedPaintDC(self.puzzle_win, self.buffer)


    def OnReset(self, event):
        """Reset options to default."""

        config = self.config
        self.letter_error.SetValue(config.letter_error_color_default)
        self.letter_checked.SetValue(config.letter_checked_color_default)
        self.letter_cheat.SetValue(config.letter_cheat_color_default)
        self.graphic_error.SetValue(config.graphic_error_color_default)
        self.graphic_checked.SetValue(config.graphic_checked_color_default)
        self.graphic_cheat.SetValue(config.graphic_cheat_color_default)
        self.updateBoard(None)


    def write(self, config):
        """Save options."""

        config.letter_error_color = wx2hex_color(
                self.letter_error.GetValue())

        config.letter_checked_color = wx2hex_color(
                self.letter_checked.GetValue())

        config.letter_cheat_color = wx2hex_color(
                self.letter_cheat.GetValue())

        config.graphic_error_color = wx2hex_color(
                self.graphic_error.GetValue())

        config.graphic_checked_color = wx2hex_color(
                self.graphic_checked.GetValue())

        config.graphic_cheat_color = wx2hex_color(
                self.graphic_cheat.GetValue())

        config.show_clues = self.show_clues.IsChecked()
        config.grey_filled_clues = self.grey_filled_clues.IsChecked()
        config.flag_graphic = self.flag_graphic_cbox.IsChecked()
        config.flag_letter = self.flag_letter_cbox.IsChecked()



class SolvingPrefs(wx.Panel):
    """Prefs for browser, keyboard nav, and tournament settings."""

    def __init__(self, parent, config):
        wx.Panel.__init__(self, parent)

        one_across_label = makeHeading(self, "OneAcross / Google Lookup")
        self.browser = wx.Choice(self, wx.ID_ANY, 
                choices = [ INT_BROWSER, EXT_BROWSER ])
        if config.internal_browser:
            self.browser.SetSelection(0)
        else:
            self.browser.SetSelection(1)

        keynav_label = makeHeading(self, "Keyboard Navigation")
        self.skip_filled = _checkbox(self, 
                "Skip filled letters when entering word", config.skip_filled)
        self.end_at_word = _checkbox(self, 
                "Stop at word end when entering word", config.end_at_word)

        tourn_label = makeHeading(self, "Tournament Settings")
        self.no_cheats = _checkbox(self, 
                "Disable checking/revealing answers", 
                config.no_cheats)
        self.no_autowin = _checkbox(self, 
                "Disable auto-notification of puzzle completion",
                config.no_autowin)
        self.no_unlock = _checkbox(self, 
                "Disable puzzle solution unlocking", config.no_unlock)
        self.no_oneacross = _checkbox(self, 
                "Disable OneAcross.com assistance", config.no_oneacross)
        self.timer_autostart = _checkbox(self, 
                "Start timer on puzzle start", config.timer_autostart)
        self.no_timerpause = _checkbox(self, 
                "Disable pausing timer", config.no_timerpause)

        solving_label = makeHeading(self, "Solving Feedback")
        self.flash_correct = _checkbox(self,
                "Flash when word completed correctly",
                config.flash_correct)

        osizer = wx.BoxSizer(wx.VERTICAL)
        osizer.AddMany( [ 
                         (one_across_label, 0, wx.LEFT|wx.TOP|wx.BOTTOM, 10),
                         (self.browser, 0, wx.LEFT, 30), 
                         (10, 10),
                         (keynav_label, 0, wx.LEFT|wx.TOP|wx.BOTTOM, 10),
                         (self.skip_filled, 0, wx.LEFT, 30),
                         (self.end_at_word, 0, wx.LEFT, 30),
                         (10, 10),
                         (tourn_label, 0, wx.LEFT|wx.TOP|wx.BOTTOM, 10),
                         (self.no_cheats, 0, wx.LEFT, 30),
                         (self.no_autowin, 0, wx.LEFT, 30),
                         (self.no_unlock, 0, wx.LEFT, 30),
                         (self.no_oneacross, 0, wx.LEFT, 30),
                         (self.timer_autostart, 0, wx.LEFT, 30),
                         (self.no_timerpause, 0, wx.LEFT, 50),
                         (10,10),
                         (solving_label, 0, wx.LEFT|wx.TOP|wx.BOTTOM, 10),
                         (self.flash_correct, 0, wx.LEFT, 30),
                         (20, 20),
                         ])
        self.SetSizer(osizer)

        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdate)

    
    def OnUpdate(self, event):
        """Manage enabling of timer-pause based on timer auto-start."""

        if event.GetId() == self.no_timerpause.GetId():
            if not self.timer_autostart.IsChecked():
                event.Check(False)
                event.Enable(False)
            else:
                event.Enable(True)
        else:
            event.Skip()


    def write(self, config):
        """Save options."""

        config.internal_browser = self.browser.GetSelection() == 0
        config.skip_filled = self.skip_filled.IsChecked()
        config.end_at_word = self.end_at_word.IsChecked()
        config.no_cheats = self.no_cheats.IsChecked()
        config.no_autowin = self.no_autowin.IsChecked()
        config.no_unlock = self.no_unlock.IsChecked()
        config.no_oneacross = self.no_oneacross.IsChecked()
        config.no_timerpause = self.no_timerpause.IsChecked()
        config.timer_autostart = self.timer_autostart.IsChecked()
        config.flash_correct = self.flash_correct.IsChecked()


class StartupPrefs(wx.Panel):
    """Prefs for starting up application."""

    def __init__(self, parent, config):
        wx.Panel.__init__(self, parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        reopen_label = makeHeading(self, "On Startup")
        self.reopen = _checkbox(self, 
                "Re-open puzzles from last session", config.reopen)
        self.note_on_open = _checkbox(self,
                "Show puzzle note on open", config.note_on_open)
        self.show_tips = _checkbox(self, 
                "Show tip of the day", config.show_tips)
        self.check_upgrades = _checkbox(self, 
                "Check for upgrades", config.check_upgrades)
        self.checknow = wx.Button(self, wx.ID_ANY, "Check for Upgrades Now")

        none_label = makeHeading(self, "If No Puzzles Are Opened")
        self.web = wx.RadioButton(self, wx.ID_ANY, 
                "Show Web Puzzle chooser", style=wx.RB_GROUP)
        self.openfile = wx.RadioButton(self, wx.ID_ANY, 
                "Show standard Open File chooser")
        self.join = wx.RadioButton(self, wx.ID_ANY, 
                "Join shared puzzle with friend")
        self.nothing = wx.RadioButton(self, wx.ID_ANY, "Do nothing")


        self.read(config)

        sizer.AddMany([
                (reopen_label, 0, wx.ALL, 10),
                (self.reopen, 0, wx.LEFT, 30),
                (self.note_on_open, 0, wx.LEFT, 30),
                (self.show_tips, 0, wx.LEFT, 30),
                (self.check_upgrades, 0, wx.LEFT, 30),
                (5, 5),
                (self.checknow, 0, wx.LEFT, 30),
                (10, 10),
                (none_label, 0, wx.ALL, 10),
                (self.web, 0, wx.LEFT, 30),
                (self.openfile, 0, wx.LEFT, 30),
                (self.join, 0, wx.LEFT, 30),
                (self.nothing, 0, wx.LEFT, 30),
                (20, 20),
                ])
        self.SetSizer(sizer)
        sizer.Fit(self)

        self.Bind(wx.EVT_BUTTON, self.OnCheckNow, self.checknow)


    def OnCheckNow(self, event):
        """Check for upgrades right now."""

        busy = PBI.PyBusyInfo("Checking Version")
        wx.Yield()
        newest, update, date = newest_version_info()
        del busy
        prompt_update_version(None, newest, update, date)
        if newest == VERSION:
            wx.MessageBox("You are running the latest version: %s." % newest,
                    "Version Check")



    def read(self, config):
        """Read initial settings."""

        method = config.openmethod

        if method == "web":
            self.web.SetValue(True)
        elif method == "file":
            self.openfile.SetValue(True)
        elif method == "join":
            self.join.SetValue(True)
        elif method == "none":
            self.nothing.SetValue(True)


    def write(self, config):
        """Save settings."""

        config.reopen = self.reopen.GetValue()
        config.note_on_open = self.note_on_open.GetValue()
        config.show_tips = self.show_tips.GetValue()
        config.check_upgrades = self.check_upgrades.GetValue()

        # Convert radio selection for open method to config.

        if self.web.GetValue():
            method = "web"
        elif self.openfile.GetValue():
            method = "file"
        elif self.join.GetValue():
            method = "join"
        elif self.nothing.GetValue():
            method = "none"
        config.openmethod = method



class SharingPrefs(wx.Panel):
    """Pref for sharing: connection info, auto-connect, and invisibility."""

    def __init__(self, parent, config):
        wx.Panel.__init__(self, parent)

        label = makeHeading(self, "Google Talk/Jabber Connection Information")
        explain = wx.StaticText(self, wx.ID_ANY,
                "This is optional, but if entered, will be default" +
                " information for logging in to connections.")

        sizer = addLogOnDialogOptions(self, config)

        skip_conn_dlg_label = makeHeading(self, 
                "On Sharing or Joining a Shared Puzzle")
        self.skip_conn_dlg = _checkbox(self, 
                "Skip prompting for information and always use above", 
                config.skip_conn_dlg)

        self.invisible = _checkbox(self, "Stay invisible while connecting", 
                config.invisible)
        invisible_explain = makeHint(self,
                "If checked, this does not reveal your presence on IM" +
                " during game connecion. Others won't see\n" + 
                "you online, but your friend will have to enter" +
                " an invitation code to play with you. See help for details.")

        autoend_im_label = makeHeading(self, "In-Game Messaging")
        self.autoend_im = _checkbox(self, 
                "Sending message in game automatically returns" +
                " keyboard focus to grid", 
                config.autoend_im)
        self.im_sound = _checkbox(self, 
                "Play sound when receiving IM", config.im_sound)
        self.im_flash = _checkbox(self, 
                "Flash window when receiving IM", config.im_flash)

        outsizer = wx.BoxSizer(wx.VERTICAL)
        outsizer.AddMany([
                (label, 0, wx.LEFT|wx.TOP, 10),
                (10, 10),
                (explain, 0, wx.LEFT, 30),
                (10, 10),
                (sizer, 0, wx.LEFT, 30),
                (10, 10),
                (skip_conn_dlg_label, 0, wx.LEFT|wx.TOP|wx.BOTTOM, 10),
                (self.skip_conn_dlg, 0, wx.LEFT, 30),
                (5, 5),
                (self.invisible, 0, wx.LEFT, 30),
                (5, 5),
                (invisible_explain, 0, wx.LEFT|wx.RIGHT, 50),
                (8, 8),
                (autoend_im_label, 0, wx.LEFT|wx.TOP|wx.BOTTOM, 10),
                (self.autoend_im, 0, wx.LEFT|wx.RIGHT, 30),
                (self.im_sound, 0, wx.LEFT|wx.RIGHT, 30),
                (self.im_flash, 0, wx.LEFT|wx.RIGHT, 30),
                (20, 20),
                ])
        self.SetSizer(outsizer)
        sizer.Fit(self)

        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdate)


    def OnUpdate(self, event):
        """Only allow skip-dialog if everything filled out."""

        if event.GetId() == self.skip_conn_dlg.GetId():
            complete = ( bool(self.server.GetValue()) and
                         bool(self.username.GetValue()) and
                         bool(self.password.GetValue()))
            event.Enable(complete)
            if not complete:
                event.Check(False)
        else:
            event.Skip()
                      

    def write(self, config):
        """Save settings."""

        config.server = self.server.GetValue()
        config.username = self.username.GetValue()
        config.password = self.password.GetValue()
        config.skip_conn_dlg = self.skip_conn_dlg.GetValue()
        config.invisible = self.invisible.GetValue()
        config.autoend_im = self.autoend_im.GetValue()
        config.im_sound = self.im_sound.GetValue()
        config.im_flash = self.im_flash.GetValue()


class WebPuzzlePrefs(wx.Panel):
    """Prefs for managing web openers."""

    idx = None # which is selected now

    def __init__(self, parent, config):
        wx.Panel.__init__(self, parent)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.web_openers = config.getWebOpeners(include_disabled=True)
        self.lst = WebOpenList(self, self.web_openers)
        sizer.Add(self.lst, 0, wx.ALL, 10)

        rsizer = wx.BoxSizer(wx.VERTICAL)

        self.add = wx.Button(self, wx.ID_ANY, "Add Puzzle")
        self.delete = wx.Button(self, wx.ID_ANY, "Delete Puzzle")
        rsizer.AddMany( [ (self.add), (10, 10), (self.delete) ])

        editbox = wx.StaticBox(self, wx.ID_ANY, "Puzzle Details")
        editsizer = wx.StaticBoxSizer(editbox, wx.VERTICAL)

        name_label = wx.StaticText(self, wx.ID_ANY, "Puzzle Name")
        self.name = wx.TextCtrl(self, wx.ID_ANY)
        url_label = wx.StaticText(self, wx.ID_ANY, "URL Template")
        self.url = wx.TextCtrl(self, wx.ID_ANY)
        url_help = wx.StaticText(self, wx.ID_ANY, URL_HELP)

        url_help.SetFont(wx.Font(font_scale(9), 
                    wx.FONTFAMILY_DEFAULT, 
                    wx.FONTSTYLE_NORMAL, 
                    wx.FONTWEIGHT_NORMAL))
        url_help.SetForegroundColour("#444444")

        desc_label = wx.StaticText(self, wx.ID_ANY, "Description")
        self.desc = wx.TextCtrl(self, wx.ID_ANY)

        days_label = wx.StaticText(self, wx.ID_ANY, "Days Puzzle is Expected")
        
        days_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.d1 = wx.CheckBox(self, wx.ID_ANY, "M ")
        self.d2 = wx.CheckBox(self, wx.ID_ANY, "Tu ")
        self.d3 = wx.CheckBox(self, wx.ID_ANY, "W ")
        self.d4 = wx.CheckBox(self, wx.ID_ANY, "Th ")
        self.d5 = wx.CheckBox(self, wx.ID_ANY, "F ")
        self.d6 = wx.CheckBox(self, wx.ID_ANY, "Sa ")
        self.d7 = wx.CheckBox(self, wx.ID_ANY, "Su ")
        days_sizer.AddMany([ (self.d1), (self.d2), (self.d3), (self.d4), 
                             (self.d5), (self.d6), (self.d7) ])

        self.enabled = wx.CheckBox(self, wx.ID_ANY, "Enabled?")
        editsizer.AddMany([ ( name_label, 0, wx.BOTTOM, 3 ),
                         ( self.name, 0, wx.BOTTOM|wx.EXPAND, 10 ), 
                         ( url_label, 0, wx.BOTTOM, 3 ), 
                         ( self.url, 0, wx.EXPAND ), 
                         ( url_help, 0, wx.BOTTOM, 10 ),
                         ( desc_label, 0, wx.BOTTOM, 3),
                         ( self.desc, 0, wx.BOTTOM|wx.EXPAND, 10 ),
                         ( days_label, 0, wx.BOTTOM, 3),
                         ( days_sizer ),
                         ( self.enabled, 0, wx.TOP, 10 ) ])

        rsizer.Add(editsizer, 0, wx.EXPAND|wx.TOP, 20)
        sizer.Add(rsizer, 1, wx.EXPAND|wx.ALL, 10)

        self.SetSizer(sizer)

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self.lst)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected, self.lst)
        self.Bind(wx.EVT_CHECKBOX, self.OnEnableCheck, self.enabled)
        self.Bind(wx.EVT_BUTTON, self.OnAdd, self.add)
        self.Bind(wx.EVT_BUTTON, self.OnDelete, self.delete)

        self.enabler(False)


    def OnAdd(self, event):
        """Add a blank opener to the list."""

        idx = len(self.web_openers)
        new = {'id': 'user:%s' % idx, 
               'name':'Untitled', 
               'url':'http://', 
               'days':'',
               'desc':'', 
               'enabled':True, 
               'icon': 'generic.png'}
        self.web_openers.append(new)
        
        self.lst.InsertImageStringItem(
                idx, 
                new['name'], 
                self.lst.imgl.Add(wx.Bitmap(get_icon(new['icon']))))
        self.lst.enableItem(idx, True)
        self.lst.Select(idx)
        self.lst.Focus(idx)


    def OnDelete(self, event):
        """Delete opener from the list."""

        del self.web_openers[self.idx]
        self.enabler(False)
        self.lst.DeleteItem(self.idx)
        self.name.SetValue("")
        self.url.SetValue("")
        self.desc.SetValue("")
        self.idx = None
        self.enabled.SetValue(False)
        for d in range(1, 8):
            getattr(self, 'd%s' % d).SetValue(False)
        
        
    def enabler(self, enable=True, enable_edit=False):
        """Enable/disable editing."""

        self.name.Enable(enable_edit)
        self.url.Enable(enable_edit)
        self.desc.Enable(enable_edit)
        for d in range(1, 8):
            getattr(self, 'd%s' % d).Enable(enable_edit)
        self.enabled.Enable(enable)
        self.delete.Enable(enable_edit)


    def OnItemSelected(self, event):
        """Item selected.

           Fill info and enable editing.
        """

        idx = event.GetIndex()
        opener = self.web_openers[idx]
        # Don't allow editing/deletion of "sys:" sources
        self.enabler(True, enable_edit=opener['id'].startswith('user:'))
        self.name.SetValue(opener['name'])
        self.url.SetValue(opener['url'])
        self.desc.SetValue(opener['desc'])
        for d in range(1, 8):
            getattr(self, 'd%s' % d).SetValue(str(d) in opener['days'])
        self.enabled.SetValue(opener['enabled'])
        self.idx = idx
        

    def OnItemDeselected(self, event): 
        """Item deselected.

           Save into the openers dict.
        """

        idx = event.GetIndex()
        opener = self.web_openers[idx]
        opener['name'] = self.name.GetValue()
        opener['url'] = self.url.GetValue()
        opener['desc'] = self.desc.GetValue()
        days = "".join(
                [ str(d) for d in range(1,8) 
                        if getattr(self, 'd%s' % d).IsChecked() ])
        opener['days'] = days
        opener['enabled'] = self.enabled.IsChecked()
        self.lst.SetItemText(idx, self.name.GetValue())


    def OnEnableCheck(self, event):
        """Update appearance of item after changing enable checkbox."""

        self.lst.enableItem(self.idx, event.IsChecked())


    def write(self, config):
        """Save preferences."""
        if self.idx is not None:
            self.lst.Select(self.idx, False)
        config.setWebOpeners(self.web_openers)



class PrefsDialog(wx.Dialog):
    """GUI Preferences Dialog."""

    def __init__(self, parent, config):
        wx.Dialog.__init__(self, parent)

        self.config = config
        self.notebook = notebook = wx.Notebook(self)

        self.appearance = AppearancePrefs(notebook, config)
        self.solving = SolvingPrefs(notebook, config)
        self.sharing = SharingPrefs(notebook, config)
        self.webpuzzle = WebPuzzlePrefs(notebook, config)
        self.startup = StartupPrefs(notebook, config)

        notebook.AddPage(self.appearance, "Appearance")
        notebook.AddPage(self.solving, "Solving")
        notebook.AddPage(self.sharing, "Sharing")
        notebook.AddPage(self.webpuzzle, "Web Puzzles")
        notebook.AddPage(self.startup, "Startup")

        sizer=wx.BoxSizer(wx.VERTICAL)
        sizer.Add(notebook)
        self.SetSizer(sizer)
        sizer.Fit(self)

        self.Bind(wx.EVT_CLOSE, self.OnClose)


    def OnClose(self, event):
        """Close and save prefs."""

        self.startup.write(self.config)
        self.sharing.write(self.config)
        self.solving.write(self.config)
        self.appearance.write(self.config)
        self.webpuzzle.write(self.config)
        self.Destroy()
        self.EndModal(wx.ID_OK)



def showPrefsDialog(config):
    """Show preferences and update open puzzles afterwards.
    
    This is the only part of this intended to be called from outside
    this module.
    """

    dlg = PrefsDialog(None, config)
    dlg.ShowModal()
    dlg.Destroy()
    for w in wx.GetApp().windows:
        if not w.dummy:
            w.UpdatePrefs()



if __name__ == "__main__":
    app = wx.App()
    from xsocius.gui.config import XsociusConfig
    xconfig = XsociusConfig()
    showPrefsDialog(xconfig)
