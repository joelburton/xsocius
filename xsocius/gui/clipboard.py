"""Copy/Paste/Cut/Clear functionality."""

import wx


class ClipboardMixin:
    """Mixin class to provide clipboard access for puzzle window."""

    def __init__(self):

        # Update menus to reflect possibility of paste

        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdatePaste)

    def OnUpdatePaste(self, event):
        """Update paste menu options to reflect state of system."""

        event_id = event.GetId()
        if event_id == wx.ID_PASTE:
            event.Enable(bool(self._getClipboardText()))
        else:
            event.Skip()

    def _setClipboardText(self, text):
        """Set text on clipboard."""

        data_o = wx.TextDataObject()
        data_o.SetText(text)
        if wx.TheClipboard.IsOpened() or wx.TheClipboard.Open():
            wx.TheClipboard.SetData(data_o)
            wx.TheClipboard.Close()

    def _getClipboardText(self):
        """Get text from clipboard."""

        text_obj = wx.TextDataObject()
        rtext = ""
        if wx.TheClipboard.IsOpened() or wx.TheClipboard.Open():
            if wx.TheClipboard.GetData(text_obj):
                rtext = text_obj.GetText()
            wx.TheClipboard.Close()

        # Check to see if it's alphanumeric, so we don't try pasting
        # icons/unicode/weird stuff.
        if rtext.isalnum():
            return rtext
        else:
            return ''

    def OnCut(self, event):
        """Cut word."""

        self._setClipboardText(self.puzzle.curr_word_text())
        self.puzzle.clear_curr_word()
        self.board.DrawNow()

    def OnCopy(self, event):
        """Copy word."""

        self._setClipboardText(self.puzzle.curr_word_text())

    def OnPaste(self, event):
        """Paste word."""

        word = self._getClipboardText()
        self.puzzle.fill_curr_word(word)
        self.board.DrawNow()

    def OnClear(self, event):
        """Clear word."""

        self.puzzle.clear_curr_word()
        self.board.DrawNow()
