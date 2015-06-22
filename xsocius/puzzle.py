"""Puzzle logic.

Logic related to the in-memory representation of crossword puzzle, clues,
and cells. GUI stuff is not located here.
"""

import os.path
import logging

from xsocius import acrosslite
from xsocius.undo import UndoQueue

# There is a c-based unlocker but it may not work for all systems
# (and I have no means to compile it for Windows). Fall back on the 
# slower Python-based one.

try:
    from xsocius.unlocker import gui_unlock
    FAST_UNLOCK = True
except ImportError:
    FAST_UNLOCK = False


class DiagramlessPuzzleFormatError(Exception):
    """Cannot use diagramless puzzles."""


class Cell(object):
    """Cell."""
    
    x = None
    y = None
    xy = (None, None)
    across = None     # across clue starting here, else None
    down = None       # down clue starting here, else None
    in_across = None  # across clue this is part of, else None
    in_down = None    # down clue this is part of, else None
    black = False     # True is space is nonplayable
    answer = None     # Correct answer
    response = None   # Current user answer on board.
    circled = False   # Cell is circled
    checked = False   # User checked correctness of cell
    revealed = False  # User cheated and revealed cell
    across_cells = [] # List of across cells in this word
    down_cells = []   # List of down cells in this word
    rebus_answer = None      # Full text of solution
    rebus_response = None    # Rebus response
    highlight = False # Used to flash cells changed by friend
    flash_correct = None    # Flash when correct for a second
    pencil = False    # Answer in pencil (defaults to pen)
    
    def __init__(self, x, y, across=None, down=None, response=None,
            checked=None, answer=None, revealed=None):
        self.x = x
        self.y = y
        self.xy = (x, y)
        # Have to set these here, otherwise we'll use same copy of list
        # everywhere
        self.across_cells = []
        self.down_cells = []

        if across is not None:
            self.across = across
        if down is not None:
            self.down = down
        if response is not None:
            self.response = response
        if checked is not None:
            self.checked = checked
        if answer is not None:
            self.answer = answer
        if revealed is not None:
            self.revealed = revealed
        

    def __repr__(self):
        #return "%s%s%s" % (self.x, self.y, self.response )
        return ( "<Cell x={c.x} y={c.y} across={c.across} down={c.down}"
               " in_across={c.in_across} in_down={c.in_down}" 
               " black={c.black} answer={c.answer} response={c.response}"
               " circled={c.circled} checked={c.checked}"
               " revealed={c.revealed}>" ).format(c=self)


    def __bool__(self):
        return bool(self.response)


    def _to_state(self):
        """Return tuple of state items.

           Used for undo/redo systems; this emits everything that we
           need to track about a cell.
        """

        return (self.response, self.checked, self.revealed, self.rebus_answer)


    def _from_state(self, state):
        """Updates cell from state item.

           Used for undo/redo systems; this fixes up the cell with values
           from the state.
        """

        self.response, self.checked, self.revealed, self.rebus_answer = state


    def reset(self):
        """Start square over."""

        self.response = ''
        self.checked = False
        self.revealed = False


    def is_correct(self):
        """Is cell corect."""

        return (self.answer == self.response 
                and self.rebus_answer == self.rebus_response)


        
class Clue(object):
    """Puzzle clue."""

    def __init__(self, num=None):
        if num:
            self.num = num
    
    num = 0                     # Clue number
    across = None               # Across clue for this #, if any
    down = None                 # Down clue for this #, if any
    across_idx = None           # Index # of this clue in across list
    down_idx = None             # Index $# of this clue in down list
    cell = Cell(None, None)     # Cell for this clue
    across_filled = False       # True if filled-out-across
    down_filled = False         # True if filled-out-down

    def __repr__(self):
        return "<Clue num=%s across='%s' down='%s' across_idx=%s down_idx=%s" \
               " cell=%s>" % (
                        self.num, self.across, self.down, self.across_idx, 
                        self.down_idx, self.cell.xy)
    

    def update_filled(self, direction):
        """True if grid for clue filled in (regardless if correct.)
        
        This both calculates the current value and caches it in across_filled
        or down_filled. These are used to grey out clues in the clue lists
        once the corresponding word in the puzzle has been filled in.
        """

        if direction == "across":
            out = self.across_filled = all(
                    [ cell.response for cell in self.cell.across_cells ])
         
        else:
            out = self.down_filled = all(
                    [ cell.response for cell in self.cell.down_cells ])

        return out
         
    
    
class Puzzle(object):
    """Crossword puzzle.

    Contains logic for puzzle. The puzzle is read off disk (by separate code)
    and then this creates the in-memory puzzle representation. Contains logic
    for moving around puzzle, checking correctness, etc.

    Does not contain GUI-specific code.
    """
    
    grid = []
    clues = [None]  # First clue is null clue, so clue #1 = clues[1]
    
    height = 0
    width = 0
    title = ""
    author = ""
    copyright = ""
    note = ""
    
    curr_cell = None
    curr_dir = "across"

    puzzle_correct_flag = False

    path = None
    dirname = None
    filename = None
    filename_no_ext = None

    dirty = False  # unsaved changes
    xmpp = None    # not connected to chat now
    timer_start = 0
    timer_start_paused = True

    grey_filled_clues = False
    

    def load(self, path):
        """Load file and setup puzzle."""
        
        self.path = path = os.path.abspath(path)
        self.dirname, self.filename = os.path.split(path)
        self.filename_no_ext = os.path.splitext(self.filename)[0]
        
        pfile = acrosslite.read(path)
        if pfile.puzzletype == acrosslite.PuzzleType.Diagramless:
            raise DiagramlessPuzzleFormatError("Can't use diagramless puzzles")
        self._setup(pfile)
        

    def _setup(self, pfile):
        """Examine board and number clues."""

        self.pfile = pfile
        self.clues = [None]
        self.title = pfile.title
        self.author = pfile.author
        self.copyright = pfile.copyright
        self.note = pfile.notes
        self.height = height = pfile.height
        self.width = width = pfile.width
        self.grid = [[Cell(x, y) for y in range(height)] for x in range(width)]

        raw_clues = pfile.clue_numbering()

        # Translate file's answers, responses, and "markup" (errors, circles, 
        # etc) from a flat-list to our x,y matrix format.

        def _to_matrix(v, h, w):
            return { (x,y): v[x+(y*w)] for y in range(h) for x in range(w) }

        answers = _to_matrix(pfile.solution, height, width)
        responses = _to_matrix(pfile.fill, height, width)

        if pfile.has_markup():
            markup = pfile.markup().markup
        else:
            markup = [0 for i in range(height * width)]

        markup = _to_matrix(markup, height, width)

        if pfile.has_rebus():
            rebus = pfile.rebus().table
            rebus_map = pfile.rebus().solutions
            rebus_fill = pfile.rebus().fill
        else:
            rebus = [0 for i in range(height * width)]


        rebus = _to_matrix(rebus, height, width)
        
        #--- Process grid

        def _translate_response(r):
            if r == "-":
                return ""      
            return r
        
        for y in range(height):
            for x in range(width):
                cell = self.grid[x][y]
                if responses[x,y] == ".":
                    cell.black = True
                    continue
                cell.answer = answers[x,y]
                cell.response = _translate_response(responses[x,y])

                # Set states from binary coded markup in file
                _markup = markup[x,y]
                cell.checked =  bool(
                        _markup & acrosslite.GridMarkup.Incorrect or 
                        _markup & acrosslite.GridMarkup.PreviouslyIncorrect)
                cell.revealed = bool(_markup & acrosslite.GridMarkup.Revealed)
                cell.circled = bool(
                        markup[x,y] & acrosslite.GridMarkup.Circled)

                # Set rebus stuff
                if rebus[x,y]:
                    cell.rebus_answer = rebus_map[rebus[x,y]-1]
                    idx = y*width + x
                    cell.rebus_response = rebus_fill.get(y*width + x)

                

        #--- Process clues

        # First, make array to hold clues. 
        nclues = max( 
                [ c['num'] for c in raw_clues.down + raw_clues.across  ] )
        self.clues = [None] + [ Clue() for i in range(nclues) ]

        # Iterate over across clues
        #
        # For each, gather clue info and then update cell info in grid

        for idx, aclue in enumerate(raw_clues.across):
            num = aclue['num']

            # Get our clue from list and update basics.
            clue = self.clues[aclue['num']]
            clue.across = aclue['clue']
            clue.num = num
            clue.across_idx = idx
            
            # Get cell (convert AL flat format to our matrix) and update cell
            _pos = aclue['cell']
            y = _pos // width
            x = _pos % width
            cell = self.grid[x][y]
            clue.cell = cell
            cell.across = clue

            # Update all cells in this word
            word = [ self.grid[ox][y] for ox in range(x, x+aclue['len']) ]
            for cell in word:
                cell.in_across = clue
                cell.across_cells = word
        
        # Do same thing for down clues

        for idx, dclue in enumerate(raw_clues.down):
            num = dclue['num']

            clue = self.clues[dclue['num']]
            clue.down = dclue['clue']
            clue.num = num
            clue.down_idx = idx
            
            _pos = dclue['cell']
            y = _pos // width
            x = _pos % width
            cell = self.grid[x][y]
            clue.cell = cell
            cell.down = clue

            word = [ self.grid[x][oy] for oy in range(y, y+dclue['len']) ]
            for cell in word:
                cell.in_down = clue
                cell.down_cells = word

        # Parse timer state
        # Format is 45,0  (seconds, is-paused)
        if pfile.has_timer():
            self.timer_start = self.pfile.timer().elapsed_sec
            self.start_paused = self.pfile.timer().paused


    def initPuzzleCursor(self):
        """Set initial puzzle cursor."""

        # Start at top left of puzzle and going across
        # But this may be a black square

        x = y = 0
        while self.grid[x][y].black:
            x += 1
            if x >= self.width:
                x = 1
                y += 1

        self.curr_cell = self.grid[x][y]

        if self.curr_cell.across:
            self.curr_dir = "across"
        else:
            self.curr_dir = "down"

        # Create initial state of puzzle, so we can revert back to it.
        # Create undo queue and put initial state into it
        # Only do this if this is the start of a puzzle (not the restart
        # of a puzzle)
        if not hasattr(self, 'undo'):
            state = self._stateToUndoPackage()
            self.undo = UndoQueue(state)
            self.revert_state = state

        # Clear the list of clues-recently-completed

        self.clues_completed_queue = []


    def setResponse(self, cell, response, rebus=None, noecho=False, 
            pencil=False):
        """Set response."""

        # Use only when setting a single cell at a time, since this
        # adds an undopoint. If changing more than one letter (or letter state)
        # at a time, the entire change should be made directly, then
        # add_undo() called.

        cell.response = response
        cell.pencil = pencil

        if rebus:
            cell.rebus_response = rebus
        if self.xmpp is not None and not noecho:
            if response:
                self.xmpp.send_set(cell.x, cell.y, response, rebus)
            else:
                self.xmpp.send_clear([(cell.x, cell.y)])

        self.add_undo()


    def break_encryption(self):
        """Break encryption of puzzle."""

        pfile = self.pfile
        # Now done with Cython so it's even faster :)

        unscrambled, key = gui_unlock(
                self.width, 
                self.height, 
                pfile.solution.encode(), 
                pfile.scrambled_cksum)
        print(unscrambled, key)
        if not unscrambled:
             return False

        # Reload puzzle
        pfile.solution = unscrambled.decode()
        pfile.scrambled_cksum = 0
        pfile.solution_state = acrosslite.SolutionState.Unlocked
        self.updateAnswers()
        return key


    def updateAnswers(self):
        """Update our answers from underlying puzzle object.

           Called after puzzle is locked/unlocked.
        """

        def _to_matrix(v, h, w):
            return { (x,y): v[x+(y*w)] 
                    for y in range(h) for x in range(w) }

        answers = _to_matrix(self.pfile.solution, self.height, self.width)

        for y in range(self.height):
            for x in range(self.width):
                if not answers[x,y] == ".":
                    self.grid[x][y].answer = answers[x,y]

        # We can't undo/redo after locking/unlocking, so reset the undo system.

        state = self._stateToUndoPackage()
        self.undo = UndoQueue(state)
        self.revert_state = state

    #--- Undo stuff


    def revert_puzzle(self):
        """Revert to saved condition."""

        # We keep track of the revert_state in self.revert_state;
        # this is updated on first run of puzzle and at every save.

        self._undoPackageToState(self.revert_state)
        self.add_undo()


    def save_state(self):
        """Save state of puzzle."""

        # Called when puzzle is saved, so we can revert back to it
        # if requested.

        self.revert_state = self._stateToUndoPackage()


    def _stateToUndoPackage(self):
        """Package together a simple state object for undo/redo."""

        # This should be everything that changes about the puzzle;
        # e.g.: we don't need clues as they don't change during solving.
        #
        # To avoid complexities with deepcopy, we get just basic info about
        # the cells in the grid

        package = {
            'grid': [[ c._to_state() for c in y] for y in self.grid ],
            'curr_x': self.curr_cell.x,
            'curr_y': self.curr_cell.y,
            'curr_dir': self.curr_dir }

        return package


    def _undoPackageToState(self, package):
        """Change state to reflect package from undo/redo."""

        for x in range(self.width):
            for y in range(self.height):
                self.grid[x][y]._from_state( package['grid'][x][y] )
        self.curr_cell = self.grid[package['curr_x']][package['curr_y']]
        self.curr_dir = package['curr_dir']


    def doUndo(self):
        """Restore undo package -> current state."""

        package = self.undo.undo()
        self._undoPackageToState(package)


    def doRedo(self):
        """Restore redo package -> curent state."""

        package = self.undo.redo()
        self._undoPackageToState(package)

    
    def add_undo(self):
        """Add undo state.
        
        Call this on any change that should be undo-able.
        """

        package = self._stateToUndoPackage()
        self.undo.add(package)

        # Free ride here; since anything that makes an undopoint also
        # means the puzzle is dirty, set this.
        self.dirty = True

        self.on_any_change()


    def check_clue_fill_change(self, force=True):
        """Check for changes in clue fills.
        
        This is used to grey-out completed clues in the puzzle.
        It is called on any change to the puzzle.

        If the status of a clue changes from 
        completed <-> not completed, this is added to
        clues_completed_queue. The GUI can use this to
        update the presentation of these clues.

        If force is selected, all clues are added to the
        queue--this is used when the puzzle is opened, or
        if we change our preferences around greying-out clues.
        """

        for c in self.clues[1:]:
            if c.across:
                old = c.across_filled
                filled = c.update_filled("across")
                if filled != old or force:
                    self.clues_completed_queue.append((
                            "across", c.across_idx, filled))
            if c.down:
                old = c.down_filled
                filled = c.update_filled("down")
                if filled != old or force:
                    self.clues_completed_queue.append((
                            "down", c.down_idx, filled))


    def on_any_change(self, skip_check_finished=False):
        """Stuff to do on any update.

        Called from add_undo (since many changes go through that)
        but should be called from ANY place that changes grid.
        For example, in sharing, changes made by another player
        bypass add_undo (since they're not undoable) but do
        call here directly.
        """

        # Since we just made a change, let's see if the puzzle
        # is correct -- if so, set a flag that the GUI will notice
        # during an idle period so it can notify the user

        if self.is_puzzle_correct() and not skip_check_finished:
            self.puzzle_correct_flag = True

        # Update clues-filled

        if self.grey_filled_clues:
            self.check_clue_fill_change()

        # Do anything GUI needs here
        if hasattr(self, 'gui'):
            self.gui.on_any_change()


    #--- Moving cursor


    def move(self, cell, dx, dy, stay_in_word=False, skip_filled=False):
        """Find new Cell that is delta-x and delta-y from given Cell.
        
        Skip over black squares. If edge of puzzle is reached, return
        original Cell.
        """
        
        x = cell.x
        y = cell.y
        
        x = x + dx
        while dx and x >= 0 and x < self.width:
            black = self.grid[x][y].black
            if not black and (not skip_filled or not self.grid[x][y].response):
                break
            if black and stay_in_word:
                x = cell.x
                break
            x = x + dx
        else:
            x = cell.x  # Can't move; only black beyond us
                
        y = y + dy
        while dy and y >= 0 and y < self.height:
            black = self.grid[x][y].black
            if not black and (not skip_filled or not self.grid[x][y].response):
                break
            if black and stay_in_word:
                y = cell.y
                break
            y = y + dy
        else:
            y = cell.y  # Can't move; only black beyond us
                
        return self.grid[x][y]
        

    def next_word(self, cell, dx, dy):
        """Skip to next word in same direction."""

        x = cell.x
        y = cell.y

        if dx < 0 and not cell == cell.across_cells[0]:
            # Not at start of word, move there
            x = cell.across_cells[0].x

        elif dx:
            while x >= 0 and x < self.width and not self.grid[x][y].black:
                x += dx
            if x == self.width or x < 0:
                x = cell.x
            else:
                # Found black cell
                while x >= 0 and x < self.width and self.grid[x][y].black:
                    x += dx
                if x == self.width or x < 0:
                    x = cell.x
                else:
                    # Found next/prev word, move to first letter
                    x = self.grid[x][y].across_cells[0].x

        if dy < 0 and not cell == cell.down_cells[0]:
            # Not at start of word, move there
            y = cell.down_cells[0].y

        elif dy:
            while y >= 0 and y < self.height and not self.grid[x][y].black:
                y += dy
            if y == self.height or y < 0:
                y = cell.y
            else:
                # Found black cell
                while y >= 0 and y < self.height and self.grid[x][y].black:
                    y += dy
                if y == self.height or y < 0:
                    y = cell.y
                else:
                    # Found next/prev word, move to first letter
                    y = self.grid[x][y].down_cells[0].y

        return self.grid[x][y]


    def switch_dir(self):
        """Switch our direction on puzzle."""

        if self.curr_dir == "across":
            self.curr_dir = "down"
        else:
            self.curr_dir = "across"
            

    #--- Current puzzle info


    def curr_clue(self):
        """Return current clue."""

        if self.curr_dir == "across":
            return self.curr_cell.in_across.across
        else:
            return self.curr_cell.in_down.down


    def curr_word(self):
        """Return list of cells in current word."""
        
        if self.curr_dir == "across":
            return self.curr_cell.across_cells
        else:
            return self.curr_cell.down_cells
        

    def curr_word_text(self):
        """Return current word."""

        return "".join([ let.response or "?" for let in self.curr_word() ])


    def curr_word_complete(self):
        """Is current word complete?"""

        if self.curr_dir == "across":
            return all( [ bool(cell) for cell in self.curr_cell.across_cells ])
        else:
            return all( [ bool(cell) for cell in self.curr_cell.down_cells ])


    def is_puzzle_correct(self):
        """Return True if entire puzzle is filled out and correct."""
        
        if self.pfile.is_solution_locked():        
            # If puzzle is locked, we can use the underlying acrosslite lib
            # to check if it is correct--but we first have to "push" our
            # changes to the grid responses down into the format that the
            # library uses, and then use that for comparison.
            fill = ""
            for y in range(self.height):
                for x in range(self.width):
                    cell = self.grid[x][y]

                    if cell.black:
                        fill += "."
                    elif not cell.response:
                        fill += "-"
                    else:
                        fill += cell.response
            return self.pfile.check_answers(fill)

        else:
            for row in self.grid:
                for cell in row:
                    if not cell.is_correct():
                        return False
            return True


    #---- Clear and Paste


    def clear_curr_word(self, noecho=False):
        """Clear current word."""

        for letter in self.curr_word():
            letter.response = None
            letter.rebus = None

        self.add_undo()

        if self.xmpp is not None and not noecho:
            self.xmpp.send_clear( [ c.xy for c in self.curr_word() ] )  


    def fill_curr_word(self, word):
        """Fill in current word.

           Used when pasting from clipboard.
        """

        curr_word = self.curr_word()
        for i, letter in enumerate(word):

            if i == len(curr_word): 
                # Reached end of word on board, stop trying to paste in rest
                break

            curr_word[i].response = letter
            if self.xmpp is not None:
                self.xmpp.send_set(curr_word[i].x, curr_word[i].y, letter)

        self.add_undo()


    #---- Check letter/words/puzzle


    def _check_letter(self, cell):
        """Check letter."""

        # Use internally; doesn't send updates via XMPP or add undopoint.

        if not cell.response: 
            return

        if not cell.is_correct():
            cell.checked = True
            return True


    def is_curr_word_correct(self):
        """Is current word complete and correct?

        Returns True if so, False if complete and wrong, and None if not done.
        """

        if not self.curr_word_complete():
            return None

        for cell in self.curr_word():
            if not cell.is_correct():
                return False
   
        return True


    def check_letter(self):
        """Check letter under cursor."""

        if self._check_letter(self.curr_cell):
            self.add_undo()
            if self.xmpp is not None:
                self.xmpp.send_check([self.curr_cell.xy])
            return True


    def check_word(self):
        """Check word under cursor."""

        changed = False
        for cell in self.curr_word():
            if self._check_letter(cell):
                changed = True
        if changed:
            if self.xmpp is not None:
                self.xmpp.send_check([ c.xy for c in self.curr_word() ])
            self.add_undo()
            return True


    def check_puzzle(self, noecho=False):
        """Check entire puzzle.
        
        If noecho is true, this is being called by a friend of the person
        who actually did the check--so we'll get the new highlights, too.
        """

        changed = False
        for x in self.grid:
            for y in x:
                if self._check_letter(y):
                    changed = True
        if changed:
            if self.xmpp is not None and not noecho:
                # Send our friend a request to do same, but only if we were
                # the person who actually requested the check.
                self.xmpp.send_check([("*","*")])
            self.add_undo()
            return True


    #----- Reveal letter/words/puzzle


    def _reveal_letter(self, cell):
        """Reveal letter under cursor."""

        # Use internally; doesn't send updates via XMPP or add undopoint.

        if cell.response != cell.answer:
            cell.response = cell.answer
            cell.rebus_response = cell.rebus_answer 
            cell.checked = True
            cell.revealed = True
            return True


    def reveal_letter(self):
        """Reveal letter under cursor."""

        if self._reveal_letter(self.curr_cell):
            self.add_undo()
            if self.xmpp is not None:
                self.xmpp.send_reveal([self.curr_cell.xy])
            return True


    def reveal_word(self):
        """Reveal word under cursor."""

        changed = False
        for cell in self.curr_word():
            if self._reveal_letter(cell):
                changed = True
        if changed:
            if self.xmpp is not None:
                self.xmpp.send_reveal([ c.xy for c in self.curr_word() ])
            self.add_undo()
            return True


    def reveal_puzzle(self, noecho=False):
        """Reveal entire puzzle."""

        changed = False
        for x in self.grid:
            for y in x:
                if self._reveal_letter(y):
                    changed = True
        if changed:
            if self.xmpp is not None and not noecho:
                self.xmpp.send_reveal([("*","*")])
            self.add_undo()
            return True


    def reveal_incorrect(self):
        """Reveal entire puzzle, but only for incorrect letters"""

        changed = False
        for x in self.grid:
            for y in x:
                if y.response and self._reveal_letter(y):
                    changed = True
        if changed:
            self.add_undo()
            return True


    #---- Save/Save As

    def update_pfile(self):
        """Update underlying pfile for save."""

        # Write state changes back to pfile and use underlying save

        fill = ""
        mkup = []
        rebus = self.pfile.rebus()

        for y in range(self.height):
            for x in range(self.width):
                cell = self.grid[x][y]

                # Fill = repsponse
                if cell.black:
                    fill += "."
                elif not cell.response:
                    fill += "-"
                else:
                    fill += cell.response

                if cell.rebus_response:
                    rebus.fill[y * self.width + x] = cell.rebus_response

                # Markup
                m = acrosslite.GridMarkup.Default
                if cell.checked and cell.is_correct():
                    m = m | acrosslite.GridMarkup.PreviouslyIncorrect
                elif cell.checked:
                    m = m | acrosslite.GridMarkup.Incorrect
                if cell.revealed:
                    m = m | acrosslite.GridMarkup.Revealed
                if cell.circled:
                    m = m | acrosslite.GridMarkup.Circled
                mkup.append(m)

        self.pfile.fill = fill
        self.pfile.markup().markup = mkup

        # Save timer
        self.pfile.extensions[acrosslite.Extensions.Timer] = "%s,%s" % (
                self.timer_time, int(not self.timer_running))


    def save_puzzle(self, path=None):
        """Save puzzle."""

        # Save the puzzle state so we can revert-to-saved

        logging.debug("Puzzle saving: %s", path)
        self.save_state()
        self.update_pfile()

        if not path:
            path = self.path

        self.pfile.save(path)

        logging.info("Puzzle saved: %s", path)
        self.dirty = False

         
            

if __name__ == "__main__":
    p = Puzzle()
    p.load('/Users/joel/test.puz')
    p.pfile.save('/tmp/out.puz')
