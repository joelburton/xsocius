"""Crossword GUI board area."""

import logging

import wx
from xsocius.gui.utils import font_scale


class PresentationBoardMixin:
    """Presentation components for board.

       Mixin that has just the drawing support functions; used by both the
       GUI board and the print board.
    """

    # Override this for printout behavior
    printout = False

    # Override this for "demo" behavior (used in prefs panel to show appearance of a mini-board
    demo = False

    # In this mixin, we can't assume that self=puzzle window, so pass puzzle to our methods

    def PrepareDrawSizing(self, bufwidth, bufheight, startx=0, starty=0):
        """Draw grid and numbers."""

        puzzle = self.puzzle

        # Height, width of cells is size of window/size of crossword

        if not self.printout and not self.demo:
            # Make room for border
            border = 2
        else:
            border = 0

        w_size = (bufwidth - border) // puzzle.width
        h_size = (bufheight - border) // puzzle.height
        rect_size = self.rect_size = min(w_size, h_size)
        logging.debug("DrawSize rect_size = %s", rect_size)

        # The size of the graphic board is almost certainly smaller than the allocated space (
        # since every rect has to be the same size). Calculate Leftover space and use this to
        # center game board in space.

        if self.printout or self.demo:
            # Start at given origin
            hoff = startx
            voff = starty
        else:
            # Center in space
            w = puzzle.width * rect_size
            h = puzzle.height * rect_size
            hoff = (bufwidth - w) / 2
            voff = (bufheight - h) / 2
            self.highlight_rect = (hoff - border / 2,
                                   voff - border / 2,
                                   w + border,
                                   h + border)

        # Calculate positions and sizes of all cells, using offsets above
        # to center

        for x in range(puzzle.width):
            for y in range(puzzle.height):
                r = self.rects[x][y]
                r.X = x * rect_size + hoff
                r.Y = y * rect_size + voff
                r.Width = rect_size
                r.Height = rect_size


        # Font is 3/4 height of cell, helvetica, non-italic, bold

        font_size = rect_size * 0.7
        if wx.Platform == "__WXMSW__":
            fs = font_size * 0.65
            self.letterFont = wx.Font(fs,
                                      wx.FONTFAMILY_DEFAULT,
                                      wx.FONTSTYLE_NORMAL,
                                      wx.FONTWEIGHT_BOLD)
            self.pencilFont = wx.Font(fs,
                                      wx.FONTFAMILY_DEFAULT,
                                      wx.FONTSTYLE_NORMAL,
                                      wx.FONTWEIGHT_NORMAL)
        else:
            self.letterFont = wx.Font((font_size, font_size),  # 2to3
                                      wx.FONTFAMILY_DEFAULT,
                                      wx.FONTSTYLE_NORMAL,
                                      wx.FONTWEIGHT_BOLD)
            self.pencilFont = wx.Font((font_size, font_size),
                                      wx.FONTFAMILY_DEFAULT,
                                      wx.FONTSTYLE_NORMAL,
                                      wx.FONTWEIGHT_NORMAL)

        # Special font is used for rebus entries (>1 letter in square)

        if wx.Platform == "__WXMSW__":
            fs = rect_size // 4
            self.specialFont = wx.Font(fs,
                                       wx.FONTFAMILY_DEFAULT,
                                       wx.FONTSTYLE_NORMAL,
                                       wx.FONTWEIGHT_BOLD)
        else:
            self.specialFont = wx.Font((font_size / 2, font_size / 2),
                                       wx.FONTFAMILY_DEFAULT,
                                       wx.FONTSTYLE_NORMAL,
                                       wx.FONTWEIGHT_BOLD)

        # Numbering font for clue #s in grid

        if wx.Platform == "__WXMSW__":
            fs = rect_size // 3.5
            self.numberFont = wx.Font(fs,
                                      wx.FONTFAMILY_DEFAULT,
                                      wx.FONTSTYLE_NORMAL,
                                      wx.FONTWEIGHT_NORMAL)
        else:
            self.numberFont = wx.Font(
                (font_size * 0.58, font_size * 0.58),
                wx.FONTFAMILY_DEFAULT,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD)

    def setupColors(self):
        """Setup colors for drawing."""

        logging.debug("setupColors")
        config = wx.GetApp().config

        self.letter_normal_color = "Black"
        self.letter_pencil_color = "#444444"
        self.letter_error_color = config.letter_error_color
        self.letter_checked_color = config.letter_checked_color
        self.letter_cheat_color = config.letter_cheat_color
        self.graphic_error_color = config.graphic_error_color
        self.graphic_checked_color = config.graphic_checked_color
        self.graphic_cheat_color = config.graphic_cheat_color

        self.graphic_error_pen = wx.Pen(self.graphic_error_color)
        self.graphic_checked_pen = wx.Pen(self.graphic_checked_color)
        self.graphic_cheat_pen = wx.Pen(self.graphic_cheat_color)
        self.graphic_error_brush = wx.Brush(self.graphic_error_color)
        self.graphic_checked_brush = wx.Brush(self.graphic_checked_color)
        self.graphic_cheat_brush = wx.Brush(self.graphic_cheat_color)
        self.focus_pen = wx.Pen("#5555BB", 2)
        self.circle_pen = wx.Pen("#777777")
        self.circle_brush = wx.Brush("#DDDDDD")

        self.flag_graphic = config.flag_graphic
        self.flag_letter = config.flag_letter

        if self.printout:
            self.color_cell_pen = wx.Pen("Black", 0.75)
        else:
            self.color_cell_pen = wx.Pen("Black")

        self.cell_highlight_brush = wx.Brush("#FFBBBB")  # lit up in sharing
        self.cell_flash_brush = wx.Brush("#BBFFBB")  # curr word right
        self.cell_flashbad_brush = wx.Brush("#FF9999")  # curr word wrong
        self.cell_curr_cell_brush = wx.Brush("Gold")  # cell we're on
        self.cell_curr_word_brush = wx.Brush("Goldenrod")  # word we're in
        self.cell_black_brush = wx.Brush("Black")  # black square
        self.cell_normal_brush = wx.Brush("White")  # otherwise

        if wx.Platform == "__WXGTK__" or self.printout or self.demo:
            self.background_brush = wx.Brush("WHITE")
        else:
            self.background_brush = wx.Brush(self.GetBackgroundColour())

    def drawCells(self, width, height, grid, rects, live, showflags, dc):
        """Draw cells on grid."""

        # Draws the actual puzzle grid cells and populates it:
        # The grid is made up of individual rectangles (with the current one
        # filled with color). Then, circles are added to circled letters.
        # Then, the response letters (or words, in the case of rebus squares)
        # are filled in. Then, and checked/wrong flags are drawn in the corner.
        #
        # Clue numbers are added later.

        for x in range(width):
            for y in range(height):
                cell = grid[x][y]

                if live and self.puzzle.curr_cell == cell:  # Cursor cell
                    dc.SetBrush(self.cell_curr_cell_brush)
                elif live and cell.flash_correct is False:
                    dc.SetBrush(self.cell_flashbad_brush)
                elif live and cell.flash_correct is True:
                    dc.SetBrush(self.cell_flash_brush)
                elif live and cell in self.puzzle.curr_word():  # Current word
                    dc.SetBrush(self.cell_curr_word_brush)
                elif cell.black:  # Black square
                    dc.SetBrush(self.cell_black_brush)
                elif live and cell.highlight:
                    dc.SetBrush(self.cell_highlight_brush)
                else:
                    dc.SetBrush(self.cell_normal_brush)

                px, py, h, w = rects[x][y].Get()
                dc.SetPen(self.color_cell_pen)
                dc.DrawRectangle(px, py, h, w)

                # If cell has circle, draw it

                if cell.circled:
                    dc.SetPen(self.circle_pen)
                    dc.SetBrush(self.circle_brush)
                    dc.DrawCircle(px + w * .50, py + h * .65, w * .33)

                # Draw letter and error flags

                letter = cell.response
                if letter:

                    if cell.pencil:
                        dc.SetTextForeground(self.letter_pencil_color)
                    else:
                        dc.SetTextForeground(self.letter_normal_color)

                    if showflags and cell.checked and not cell.is_correct():
                        if self.flag_graphic:
                            # Draw triangle in upper right
                            dc.SetPen(self.graphic_error_pen)
                            dc.SetBrush(self.graphic_error_brush)
                            dc.DrawPolygon(
                                [(px + w * .66, py + 1),  # TL of triangle
                                 (px + w - 1, py + 1),  # TR of triangle
                                 (px + w - 1, py + h * .33 - 1)])  # BR of triangle
                        if self.flag_letter:
                            dc.SetTextForeground(self.letter_error_color)

                    elif showflags and cell.revealed:
                        if self.flag_graphic:
                            # Draw square in upper right
                            dc.SetPen(self.graphic_cheat_pen)
                            dc.SetBrush(self.graphic_cheat_brush)
                            dc.DrawRectangle(px + w * 0.75 - 1, py + 1, w / 4, h / 4)
                        if self.flag_letter:
                            dc.SetTextForeground(self.letter_cheat_color)

                    elif showflags and cell.checked:
                        if self.flag_graphic:
                            # Draw triangle in upper right
                            dc.SetPen(self.graphic_checked_pen)
                            dc.SetBrush(self.graphic_checked_brush)
                            dc.DrawPolygon(
                                [(px + w * .66, py + 1),  # TL of triangle
                                 (px + w - 1, py + 1),  # TR of triangle
                                 (px + w - 1, py + h * .33 - 1)])  # BR of triangle
                        if self.flag_letter:
                            dc.SetTextForeground(self.letter_checked_color)


                    # If letter is len>1, change to smaller font and truncate
                    # if >4

                    if cell.rebus_response:
                        dc.SetFont(self.specialFont)
                        letter = cell.rebus_response
                        if len(letter) > 4:
                            letter = letter[:3] + b"..."
                    elif cell.pencil:
                        dc.SetFont(self.pencilFont)
                    else:
                        dc.SetFont(self.letterFont)

                    # Calculate size of letter and position 
                    # centered and bottom of cell

                    textw, texth = dc.GetTextExtent(letter)
                    txtx_offset = (w - textw) / 2
                    txty_offset = (h - texth) / 1.10
                    dc.DrawText(letter, px + txtx_offset, py + txty_offset)

    def drawNums(self, clues, rects, dc):
        """Draw clue numbers on grid."""

        dc.SetTextForeground("#111111")
        dc.SetFont(self.numberFont)

        for clue in clues[1:]:
            num = clue.num
            x, y = clue.cell.xy
            px, py, h, w = rects[x][y].Get()
            dc.DrawText(str(num), px + 1, py)

    def DrawBoard(self, dc):
        """Draw puzzle grid and numbers."""

        puzzle = self.puzzle

        # Live mode shows where you are on board, etc
        live = not self.printout and not self.demo

        # Don't show err/check/cheat flags if we're a printout or if puzzle 
        # locked (since they'd be wrong anyway). Always show when demo
        showflags = self.demo or (
            not self.printout and not puzzle.pfile.is_solution_locked())

        if live:
            dc.SetBackground(self.background_brush)
            dc.Clear()
            # if self.HasFocus():
            if self.FindFocus() == self:
                dc.SetPen(self.focus_pen)
                dc.DrawRectangle(*self.highlight_rect)

        self.drawCells(puzzle.width,
                       puzzle.height,
                       puzzle.grid,
                       self.rects,
                       live,
                       showflags,
                       dc)
        self.drawNums(puzzle.clues, self.rects, dc)


class Board(wx.Window, PresentationBoardMixin):
    """Crossword GUI board area."""

    reInitBuffer = False

    def __init__(self, parent):
        wx.Window.__init__(self, parent, size=(200, 200),
                           style=wx.NO_FULL_REPAINT_ON_RESIZE | wx.WANTS_CHARS)

        # Stash some useful pointers to other system bits.

        self.puzzle_window = self.GetTopLevelParent()
        self.puzzle = self.puzzle_window.puzzle
        self.clues = self.puzzle.clues
        self.grid = self.puzzle.grid
        self.height = self.puzzle.height
        self.width = self.puzzle.width

        # Create virtual rectangles that will create grid.

        self.rects = [[wx.Rect()
                       for y in range(self.height)]
                      for x in range(self.width)]

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

        self.Bind(wx.EVT_SET_FOCUS, self.IHaveFocus)

        self.setupColors()
        self.setupSkipLetters()
        # self.OnSize(None)

        # Might get filled with digits to jump-to-clue
        self.jump_to_clue_stack = []

    def IHaveFocus(self, event):
        """Board has focus, light it up and turn off lighting elsewhere."""

        logging.debug("board has highlight")
        self.puzzle_window.across_clues.highlight(
            self.puzzle_window.across_clues.curr)
        self.puzzle_window.down_clues.highlight(
            self.puzzle_window.down_clues.curr)
        self.DrawNow()

    def unfocusBoard(self):
        """Called when focus moves from board."""

        # There's nothing we have to do for now except update.
        self.DrawNow()

    def setupSkipLetters(self):
        """Setup option to skip letters if filled out."""

        # Called on setup and after prefs updated

        config = wx.GetApp().config
        self.skip_filled = config.skip_filled
        self.end_at_word = config.end_at_word

    def OnSize(self, event):
        """Window was resized; redraw."""

        w, h = self.GetSize()
        logging.debug("board real OnSize w, h = %s, %s", w, h)

        if w > 0 and h > 0:
            self.buffer = wx.Bitmap(w, h)
            self.PrepareDrawSizing(w, h)
            self.DrawNow()

        event.Skip()

    def DrawNow(self):
        """Redraw window right now."""

        logging.debug("DrawNow")

        dc = wx.MemoryDC()
        dc.SelectObject(self.buffer)
        self.DrawBoard(dc)
        del dc
        self.Refresh()
        self.Update()

        logging.debug("DrawNow done")

    def OnPaint(self, event):
        """Called when window needs to be updated."""

        # All we have to do is create a DC; we don't do anything with it

        wx.BufferedPaintDC(self, self.buffer)

    def OnLeftDown(self, event):
        """Mouse button pushed; select cell where click was."""

        logging.debug("board OnLeftDown")

        # Focus on board, figure out where click was in grid.
        # If black square, ignore it. Else: if we're already
        # in this cell, interpret the click to mean switch direction,
        # otherwise, go to this cell in the same direction.

        self.SetFocus()
        p = event.GetPosition()
        for x in range(self.width):
            for y in range(self.height):
                if self.rects[x][y].Contains(p):
                    if self.grid[x][y].black:
                        return
                    clicked_in = self.grid[x][y]
                    if self.puzzle.curr_cell == clicked_in:
                        self.switch_dir()
                    else:
                        self.puzzle.curr_cell = clicked_in
                        self.updateClueHighlight()
                        self.DrawNow()
                        return

    def _handle_arrow(self, event, direction, dx, dy):
        """Handle arrow movement."""

        # Called by arrows in OnKeyDown

        if event.AltDown():
            self.MoveWord(dx, dy)
        elif event.ControlDown():
            self.MoveSelection(dx, dy, stay_in_word=False, skip_filled=True)
        elif self.puzzle.curr_dir != direction:
            self.switch_dir()
            # If current cell is filled and "skip filled"
            if self.puzzle.curr_cell.response and self.skip_filled:
                self.move_continue(dx or dy,
                                   stay_in_word=self.end_at_word,
                                   skip_filled=self.skip_filled)
        else:
            self.MoveSelection(dx, dy)

    def jump_to_clue_go(self):
        """Jump to clue that user has keyed in.

        This is called after a delay following numeric keystrokes or
        when ENTER is pressed. It moves to the chosen clue and then
        clears the stack of digits entered.
        """

        if not self.jump_to_clue_stack:
            # Already happened via ENTER
            return

        cnum = int("".join(self.jump_to_clue_stack))
        self.jump_to_clue_stack = []

        for c in self.clues[1:]:
            if c.num == cnum:
                if c.across:
                    direction = "across"
                else:
                    direction = "down"
                self.moveDirectTo(c.cell, direction)

        for w in self.jump_to_clue_windows:
            w.Destroy()
        del self.jump_to_clue_windows

    def jump_to_clue_by_num(self, digit):
        """Manage digit entered to Jump to clue by number.
        
        The user has entered a digit, but we don't know if it's the last
        digit of the number they want. Add it to a stack of digits entered
        and set a timer to do the jump after a set period of time.
        """

        # We keep track of the digits in jump_to_clue_stack and we
        # keep track of the individual windows showing each keystroke
        # in jump_to_clue_windows.

        # First digit? Set timer to actually go in 1 sec
        if not self.jump_to_clue_stack:
            self.jump_to_clue_windows = []
            wx.CallLater(1000, self.jump_to_clue_go)

            # Append digit
        self.jump_to_clue_stack.append(digit)

        # Creat graphic and append
        w = wx.StaticText(self, wx.ID_ANY, digit,
                          pos=(10 + 35 * len(self.jump_to_clue_windows), 10))
        w.SetBackgroundColour("#FFDDDD")
        size = font_scale(32)
        w.SetFont(wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.BOLD))
        self.jump_to_clue_windows.append(w)

    def OnKeyDown(self, event):
        """Key pushed: move, fill in cell, or clear cell, as applicable."""

        x, y = self.puzzle.curr_cell.xy

        keycode = event.GetKeyCode()
        logging.debug("grid OnKeyDown keycode=%s", keycode)

        if keycode == wx.WXK_ESCAPE and self.puzzle_window.fullscreen:
            return self.puzzle_window.OnFullScreen(None)

        if ord("A") <= keycode <= ord("Z") and not event.ControlDown():
            was_filled = bool(self.grid[x][y].response)
            self.puzzle.setResponse(self.grid[x][y],
                                    chr(keycode),
                                    pencil=self.puzzle_window.pencil)
            self.move_continue(+1,
                               stay_in_word=self.end_at_word,
                               skip_filled=self.skip_filled and not was_filled)

        elif ord("0") <= keycode <= ord("9"):
            self.jump_to_clue_by_num(chr(keycode))

        elif keycode == wx.WXK_TAB and event.ShiftDown():
            if self.puzzle_window.across_clues.IsShown():
                logging.debug("Shift-Tab into down")
                self.puzzle_window.down_clues.SetFocus()

        elif keycode == wx.WXK_TAB:
            if self.puzzle_window.across_clues.IsShown():
                logging.debug("Tab into across")
                self.puzzle_window.across_clues.SetFocus()

        elif keycode == ord("/"):
            if self.puzzle_window.share_panel.IsShown():
                self.puzzle_window.msg_entry.SetFocus()

        elif keycode == wx.WXK_RETURN:
            # If we're in the middle of entering a clue # to jump to, ENTER completes this entry
            if self.jump_to_clue_stack:
                self.jump_to_clue_go()
            else:
                # Otherwise, it swaps directions
                self.switch_dir()

        elif keycode == wx.WXK_SPACE:
            self.move_continue()

        elif keycode == wx.WXK_RIGHT:
            self._handle_arrow(event, "across", +1, 0)
        elif keycode == wx.WXK_LEFT:
            self._handle_arrow(event, "across", -1, 0)
        elif keycode == wx.WXK_UP:
            self._handle_arrow(event, "down", 0, -1)
        elif keycode == wx.WXK_DOWN:
            self._handle_arrow(event, "down", 0, +1)

        elif keycode in (wx.WXK_DELETE, wx.WXK_BACK):
            self.puzzle.setResponse(self.grid[x][y], None)
            self.move_continue(-1)

    def switch_dir(self):
        """Change direction of cursor (requires re-highlighting clue)"""

        self.puzzle.switch_dir()
        self.updateClueHighlight()
        self.DrawNow()

    def move_continue(self, delta=+1, stay_in_word=False, skip_filled=False):
        """Move 1 in current direction."""

        if self.puzzle.curr_dir == "across":
            self.MoveSelection(delta, 0, stay_in_word, skip_filled)
        else:
            self.MoveSelection(0, delta, stay_in_word, skip_filled)

    def MoveSelection(self, dx, dy, stay_in_word=False, skip_filled=False):
        """Move current cell by (move) and re-draw."""

        new = self.puzzle.move(self.puzzle.curr_cell, dx, dy, stay_in_word, skip_filled)
        if new != self.puzzle.curr_cell:
            self.puzzle.curr_cell = new
            self.updateClueHighlight()

        # Even if we haven't moved, we might have been called because
        # a letter underneath us changed, so redraw

        self.DrawNow()

    def MoveWord(self, dx, dy):
        """Move to next word (+dx for right, -dx for left, +dy down, -dy up)"""

        curr = self.puzzle.curr_cell
        new = self.puzzle.next_word(curr, dx, dy)
        if new != curr:
            self.puzzle.curr_cell = new
            self.updateClueHighlight()
            self.DrawNow()

    def SpecialAnswer(self):
        """Enter special answer in cell."""

        dlg = wx.TextEntryDialog(None, 'Enter special answer', 'Special Answer')
        dlg.SetValue(self.puzzle.curr_cell.rebus_response or '')
        if dlg.ShowModal() == wx.ID_OK:
            value = str(dlg.GetValue().upper())  # convert from Unicode
            if value:
                init = value[0]
            else:
                init = None
                value = None
            self.puzzle.setResponse(self.puzzle.curr_cell, init, rebus=value)
            self.move_continue()
        dlg.Destroy()

    def updateClueHighlight(self):
        """Highlight clues in clue panes for cursor location."""

        # Deselect current clue and highlight clue for word we're in

        across_clues = self.puzzle_window.across_clues
        across_clue = self.puzzle.curr_cell.in_across
        if across_clue:
            idx = across_clue.across_idx
            across_clues.highlight(idx)  # move selection in clue list to match
            across_clues.EnsureVisible(idx)

        # ... same for down

        down_clues = self.puzzle_window.down_clues
        down_clue = self.puzzle.curr_cell.in_down
        if down_clue:
            idx = down_clue.down_idx
            down_clues.highlight(idx)  # move selection in clue list to match
            down_clues.EnsureVisible(idx)

        # Update clue label above board

        if self.puzzle.curr_dir == "across":
            if across_clue:
                # cluetext = "%sa. %s" % (across_clue.num, across_clue.across)
                cluetext = across_clue.across
            else:
                cluetext = ""
        else:
            if down_clue:
                # cluetext = "%sd. %s" % (down_clue.num, down_clue.down)
                cluetext = down_clue.down
            else:
                cluetext = ""

        self.puzzle_window.cluetext.SetLabel(cluetext)

    def moveDirectTo(self, cell, direction):
        """Move current cell to."""

        self.puzzle.curr_cell = cell
        self.puzzle.curr_dir = direction
        self.updateClueHighlight()
        self.DrawNow()
