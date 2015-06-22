"""Generic undo system."""

from collections import deque


class UndoQueue(object):
    """Queue for holding undo/redo states.

       Create with UndoQueue(initial_state, # of undo steps possible).

       After each state change, call add(state).
       Undo is possible if can_undo().
       Redo is possible if can_redo().

       Undo returns new (previous) state.
       Redo returns new (previous from future) state.

       Note that adding clears potential redos, as they are now invalid.

       The current state of the system is always at the end of _undo.
    """

    def __init__(self, state, max_steps=9):
        self._undo = deque([state], max_steps+1)
        self._redo = deque()

    def add(self, state):
        """Add current state to undo q."""

        self._undo.append(state)
        self._redo.clear()

    def undo(self):
        """Return previous state (& append current state to redo q)."""

        self._redo.append(self._undo.pop())
        return self._undo[-1]

    def redo(self):
        """Redo previously-undone state (& append current state to undo q).""" 

        item = self._redo.pop()
        self._undo.append(item)
        return item

    def can_undo(self):
        """Undo is possible?"""

        return len(self._undo) > 1

    def can_redo(self):
        """Redo is possible?"""

        return bool(self._redo)