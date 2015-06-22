"""Clue lists."""

import logging

import wx
import wx.lib.mixins.listctrl as listmix
from xsocius.gui.utils import font_scale


class BaseCluesList(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    """Lists of clues."""

    col_label = None
    this_dir = None

    # Currently selected item in the list
    # We don't use the real wx selection, since then we can't control
    # the appearance of the highlighting.

    curr = -1

    def __init__(self, parent, style=wx.LC_REPORT | wx.LC_SINGLE_SEL):
        wx.ListCtrl.__init__(self, parent, style=style)
        listmix.ListCtrlAutoWidthMixin.__init__(self)

        self.font_size = font_scale(12)

        self.puzzle_window = self.GetTopLevelParent()
        self.puzzle = self.puzzle_window.puzzle

        self.InsertColumn(0, self.col_label)

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelect)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_SET_FOCUS, self.IHaveFocus)

    def IHaveFocus(self, event):
        """Clue has focus; light it up and turn off elsewhere."""

        logging.debug("%s has focus", self.this_dir)

        self.puzzle.curr_dir = self.this_dir
        self.puzzle_window.across_clues.highlight(
            self.puzzle_window.across_clues.curr)
        self.puzzle_window.down_clues.highlight(
            self.puzzle_window.down_clues.curr)
        self.puzzle_window.board.unfocusBoard()

    def update_filled(self, idx, filled):
        """Update filled appearance for clue."""

        if idx == self.curr:
            # Never touch current clue
            return

        item = self.GetItem(idx)
        item.SetTextColour("#666666" if filled else wx.BLACK)
        self.SetItem(item)

    def highlight(self, idx):
        """Highlight the 'selected' clue and unlighted the former one."""

        logging.debug("clues highlighting %s old=%s", idx, self.curr)
        if idx == -1:
            return

        # If there was a former answer, de-select it
        if self.curr != -1 and self.curr != idx:
            old = self.GetItem(self.curr)

            # Decide the color to restore it to, depending on filled-ness
            if self.this_dir == "across":
                filled = self.puzzle.clues[old.GetData()].across_filled
                logging.debug("across highlight %s = %s",
                              old.GetData(), filled)
            else:
                filled = self.puzzle.clues[old.GetData()].down_filled
                logging.debug("down highlight %s = %s",
                              old.GetData(), filled)

            old.SetTextColour("#666666" if filled else wx.BLACK)
            old.SetBackgroundColour(wx.WHITE)
            self.SetItem(old)

        # Highlight the current answer
        item = self.GetItem(idx)
        # if self.HasFocus():
        if self.FindFocus() == self:
            item.SetBackgroundColour("#333399")
            item.SetTextColour(wx.WHITE)
        elif self.puzzle.curr_dir == self.this_dir:
            # Matching direction is white on gold
            item.SetBackgroundColour("#cc7f32")
            item.SetTextColour(wx.WHITE)
        else:
            # Other direction is dark grey on light gold
            item.SetBackgroundColour("#ffd5a2")
            item.SetTextColour("#332211")
        self.SetItem(item)

        self.curr = idx

    def populate(self, clues):
        """Populate list of clues."""

        self.puzzle = self.puzzle_window.puzzle
        for num, text in clues:
            newidx = self.Append(["%s. %s" % (num, text)])
            self.SetItemData(newidx, num)
        self.changeFontSize()

    def changeFontSize(self):
        """Update font size of all items."""

        font = wx.Font(self.font_size,
                       wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.NORMAL)

        # for i in range(self.GetItemCount()):
        #    self.SetItemFont(i, font)
        self.SetFont(font)

    def OnKeyDown(self, event):
        """Key pressed; handle TAB/SHIFT-TAB navigation among components."""

        k = event.GetKeyCode()
        logging.debug("clue OnKeyDown keycode=%s", k)

        # Return = go to board at this clue
        if k == wx.WXK_RETURN:
            self.GetTopLevelParent().board.SetFocus()
            return

        # / = Go to IM window
        elif k == ord("/"):
            if self.puzzle_window.share_panel.IsShown():
                self.puzzle_window.msg_entry.SetFocus()
                return

        # Del, Space, A-Z, 0-9: let grid handle hit
        elif (k in (wx.WXK_DELETE, wx.WXK_BACK, wx.WXK_SPACE) or
                  (k >= ord("A") and k <= ord("Z") and not event.ControlDown()) or
                  (k >= ord("0") and k <= ord("9"))):
            logging.debug("pass back to board")
            self.GetTopLevelParent().board.SetFocus()
            self.GetTopLevelParent().board.OnKeyDown(event)
            return

        elif k == wx.WXK_UP and (event.ControlDown() or event.AltDown()):
            self.highlight(0)
            self.EnsureVisible(0)
            return

        elif k == wx.WXK_DOWN and (event.ControlDown() or event.AltDown()):
            self.highlight(self.GetItemCount() - 1)
            self.EnsureVisible(self.GetItemCount() - 1)
            return

        event.Skip()

    def OnSelect(self, event):
        """Highlight word on board corresponding to clue selected."""

        # Called only when we click on the clue, not when a clue is
        # selected by moving around the board.

        idx = event.GetIndex()
        cluenum = event.GetData()
        logging.debug("onSelect idx=%s cluenum=%s", idx, cluenum)

        # We don't want to use the wx selection, so unselect the selection.
        self.Select(idx, 0)

        if idx != self.curr or self.puzzle.curr_dir != self.this_dir:
            # Move to new location on board.
            new_cell = self.puzzle.clues[cluenum].cell
            self.puzzle_window.board.moveDirectTo(new_cell, self.this_dir)

            # We don't have to call highlight() here, since moveDirectTo
            # calls updateClueHighlight, which calls it.


class AcrossCluesList(BaseCluesList):
    """Across Clues (at top of sash)"""

    col_label = "Across"
    this_dir = "across"


class DownCluesList(BaseCluesList):
    """Across Clues (at bottom of sash)"""

    col_label = "Down"
    this_dir = "down"


class CluesPanel(wx.Panel):
    """Panel that holds across and down clue lists."""

    def __init__(self, parent):
        wx.Panel.__init__(self, parent)  # , style=wx.WANTS_CHARS)

        # Make the across/down clue lists and, for easy reach, store
        # referene to them on the main puzzle window.

        puzzle_window = self.GetTopLevelParent()
        across_clues = puzzle_window.across_clues = AcrossCluesList(self)
        down_clues = puzzle_window.down_clues = DownCluesList(self)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(across_clues, 1, wx.EXPAND)
        sizer.Add(down_clues, 1, wx.EXPAND)
        self.SetSizer(sizer)
