"""Provide undo functionality to GUI."""

import wx


class UndoRedoMixin:
    """Adds undo/redo menu capabilities to puzzle window."""

    def __init__(self):
        # Update menus to reflect possibility of undo/redo
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateUndoRedoMenu)

    def OnUpdateUndoRedoMenu(self, event):
        """Update undo/redo menu options to reflect state of system."""

        event_id = event.GetId()
        if event_id == self.ID_UNDO:
            event.Enable(self.puzzle.undo.can_undo())
        elif event_id == self.ID_REDO:
            event.Enable(self.puzzle.undo.can_redo())
        else:
            event.Skip()

    def OnUndo(self, event):
        """Undo a change in UI."""

        if self.xmpp is None:
            self.puzzle.doUndo()
            self.board.updateClueHighlight()
            self.board.DrawNow()
        else:
            wx.MessageBox("You cannot use undo/redo when playing a shared game.")

    def OnRedo(self, event):
        """Redo a change in UI."""

        if self.xmpp is None:
            self.puzzle.doRedo()
            self.board.updateClueHighlight()
            self.board.DrawNow()
        else:
            wx.MessageBox("You cannot use undo/redo when playing a shared game.")
