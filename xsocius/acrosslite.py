"""AcrossLite file format parser and writer."""

# Adapted with permission from https://github.com/alexdej/

import struct
import logging
import string
import operator
from functools import reduce
import warnings
from collections import OrderedDict

HEADER_FORMAT = '''<
             H 11s        xH
             Q       4s  2sH
             12s         BBH
             H H '''

HEADER_CKSUM_FORMAT = '<BBH H H '

EXT_HEADER_FORMAT = '< 4s  H H '

MASKSTRING = b'ICHEATED'
ACROSSDOWN = b'ACROSS&DOWN'

BLACKSQUARE = '.'


def enum(**enums):
    """Create simple enum type.

    Returns a class, Enum, with the parameters set as attributes.
    """
    return type('Enum', (), enums)


PuzzleType = enum(
        Normal=0x0001,
        Diagramless=0x0401
    )

SolutionState = enum(
        Unlocked=0x0000,    # solution is available in plaintext
        Locked=0x0004       # solution is locked (scrambled) with a key  
    )

GridMarkup = enum(
        Default=0x00,              # ordinary grid cell
        PreviouslyIncorrect=0x10,  # marked incorrect at some point
        Incorrect=0x20,            # currently showing incorrect
        Revealed=0x40,             # user got a hint
        Circled=0x80               # circled
    )

Extensions = enum(
        Rebus=b'GRBS',             # grid of rebus indices
        RebusSolutions=b'RTBL',    # map of rebus solution entries
        RebusFill=b'RUSR',         # user's rebus entries
        Timer=b'LTIM',             # timer state
        Markup=b'GEXT')            # grid cell markup




def read(filename):
    """Read a .puz file and return the Puzzle object
    throws PuzzleFormatError if there's any problem with the file format
    """

    with open(filename, 'rb') as f:
        puz = Puzzle()
        puz.load(f.read())
        return puz


class PuzzleFormatError(Exception):  
    """Indicates a format error in the .puz file
    
    May be thrown due to invalid headers, invalid checksum validation, 
    or other format issues
    """


def is_blacksquare(c):
    """Is this square a black square?"""

    return c == BLACKSQUARE




class Puzzle:
    """Represents a puzzle
    """

    def __init__(self):
        """Initializes a blank puzzle
        """

        self.preamble = b''         # Preamble to file (unrelated to .puz)
        self.fileversion = b'1.3\0' # Version of .puz format with trailing \0
        self.unk1 = b'\0' * 2       # Unknown; round-tripped
        self.scrambled_cksum = 0    # Checksum of real solution
        self.unk2 = b'\0' * 12      # Unknown; round-tripped
        self.width = 0              # Grid width
        self.height = 0             # Grid height
        self.puzzletype = \
            PuzzleType.Normal       # Normal or diagrammless
        self.solution_state = \
            SolutionState.Unlocked  # Unlocked or scrambled

        self.version = '1.3'        # Stripped version of file

        self.solution = ''          # String of answer grid, eg "CATA.ARNR"
        self.fill = ''              # String of as-filled grid, same format

        self.title = ''
        self.author = ''
        self.copyright = ''

        self.clues = []             # List of clue strings

        self.notes = ''

        self.extensions = OrderedDict()

        self.postscript = b''

        self.helpers = {} # add-ons like Rebus and Markup


    def load(self, data):
        """Parse .puz data into puzzle object."""

        s = PuzzleBuffer(data)
        
        # .puz formats start with a 2-byte checksum and the magic string
        # ACROSS&DOWN. However, it's possible that there might be additional
        # stuff at the start of the file before this, and we'd like to keep
        # it for round-tripping.
        #
        # Find ACROSS&DOWN and move 2 bytes before it to the start of the 
        # checksum.

        if not s.seek_to(ACROSSDOWN, -2):
            raise PuzzleFormatError("Data does not appear to represent a puzzle.")
            
        # Keep any preamble for round-tripping
        self.preamble = s.data[:s.pos]
        
        # Unpack header
        ( cksum_gbl, 
          acrossDown, 
          cksum_hdr, 
          cksum_magic,
          self.fileversion, 
          self.unk1, 
          self.scrambled_cksum, 
          self.unk2,
          self.width, 
          self.height, 
          numclues, 
          self.puzzletype, 
          self.solution_state
        ) = s.unpack(HEADER_FORMAT)
        
        self.version = self.fileversion[:3]

        # Read solution & filled-squares as strings
        self.solution = s.read(self.width * self.height).decode('ISO-8859-1')
        self.fill = s.read(self.width * self.height).decode()

        # Read metadata as strings
        self.title = s.read_string()
        self.author = s.read_string()
        self.copyright = s.read_string()
        
        # Read clues as strings
        self.clues = [s.read_string() for i in range(numclues)]

        # Read notes
        self.notes = s.read_string()
        
        # Read extensions--markup, rebuses, timers, etc.
        # These are in chunks with a fixed header.

        ext_cksum = {}
        while s.can_unpack(EXT_HEADER_FORMAT):
            code, length, cksum = s.unpack(EXT_HEADER_FORMAT)
            ext_cksum[code] = cksum
            # Extension data is represented as a null-terminated string, 
            # but since the data can contain nulls
            # we can't use read_string.
            self.extensions[code] = s.read(length)
            s.read(1) # extensions have a trailing byte

        # Save any extra garbage at the end of the file, usually \r\n
        # for round-tripping.
        if s.can_read():
            self.postscript = s.read_to_end()

        # Valid puzzles fail these tests sometimes -- problem in the code?

        if cksum_hdr != self.header_cksum():
            warnings.warn("Header checksum does not match", UserWarning)
        if cksum_gbl != self.global_cksum():
            warnings.warn("Global checksum does not match", UserWarning)
        if cksum_magic != self.magic_cksum():
            warnings.warn("Magic checksum does not match", UserWarning)
        for code, cksum_ext in list(ext_cksum.items()):
            if cksum_ext != data_cksum(self.extensions[code]):
                warnings.warn("Extension {} checksum does not match".format(code), 
                        UserWarning)


    def has_rebus(self):
        """Does puzzle have a rebus section?"""

        return self.rebus().has_rebus()
        

    def rebus(self):
        """Return rebus section; computing the first time."""

        return self.helpers.setdefault('rebus', Rebus(self))
    
    
    def has_timer(self):
        """Does puzzle have a timer section?"""

        return self.timer().has_timer()

    
    def timer(self):
        """Return timer section; computing first time."""

        return self.helpers.setdefault('timer', Timer(self))


    def has_markup(self):
        """Does puzzle have a markup section?"""

        return self.markup().has_markup()
        

    def markup(self):
        """Return markup section; computing the first time."""

        return self.helpers.setdefault('markup', Markup(self))
        

    def clue_numbering(self):
        """Return clue numbering object; computing the first time."""

        return self.helpers.setdefault('clues', 
                DefaultClueNumbering(self.fill, 
                                     self.clues, 
                                     self.width, 
                                     self.height))
  

    def check_answers(self, fill):
        """Return True if puzzle is solved."""

        if self.is_solution_locked():
            return scrambled_cksum(fill, 
                                   self.width, 
                                   self.height) == self.scrambled_cksum
        else:
            return fill == self.solution


    #--------------- Saving puzzle

    def save(self, filename):
        """Save puzzle to disk."""

        # In case of problem with conversion, do this before overwriting file
        data = self.to_string()

        with open(filename, 'wb') as f:
            f.write(data)
            

    def to_string(self):
        """Create stringified version of puzzle data for saving."""

        # Construct a new buffer, filling in the correct information.

        s = PuzzleBuffer()

        # For any helpers (rebus, markup), call their save method, which
        # will push any changes made back the puzzle.extensions dictionary.

        for h in list(self.helpers.values()):
            if 'save' in dir(h):
                h.save()
        
        # Include any preamble text we might have found on read
        s.write(self.preamble)
        
        # Write header
        s.pack( HEADER_FORMAT,
                self.global_cksum(), 
                ACROSSDOWN, 
                self.header_cksum(), 
                self.magic_cksum(),
                self.fileversion, 
                self.unk1, 
                self.scrambled_cksum,
                self.unk2, 
                self.width, 
                self.height, 
                len(self.clues), 
                self.puzzletype, 
                self.solution_state )

        # Write solution and fill as bytestrings
        s.write(self.solution.encode())
        s.write(self.fill.encode())
        
        # Write metadata
        s.write_string(self.title)
        s.write_string(self.author)
        s.write_string(self.copyright)
        
        # Write clues as strings
        for clue in self.clues:
            s.write_string(clue)

        # Write notes as string
        s.write_string(self.notes)
        
        # Write extensions back

        for code, data in self.extensions.items():
            s.pack(EXT_HEADER_FORMAT, 
                   code,
                   len(data), 
                   data_cksum(data))

            if type(data) == type([]):
                data = bytes(data)

            if type(data) == type(""):
                data = data.encode()

            s.write(data + b'\0')
        
        # Write any trailing material for original file

        s.write(self.postscript)
        
        return s.as_bytes()


    #--------------- Locked (Scrambled Solution) Puzzles

    def is_solution_locked(self):
        """Return True if solution locked."""

        return bool(self.solution_state != SolutionState.Unlocked)
  

    def unlock_solution(self, key):
        """Unscramble solution."""

        if self.is_solution_locked():
            unscrambled = unscramble_solution(self.solution, 
                                              self.width, 
                                              self.height, 
                                              key)

            if not self.check_answers(unscrambled):
                # Unscrambling failed
                return False

            # Clear the scrambled bit and cksum
            self.solution = unscrambled
            self.scrambled_cksum = 0
            self.solution_state = SolutionState.Unlocked

        return True


    def lock_solution(self, key):
        """Scramble puzzle."""

        if not self.is_solution_locked():
            # set the scrambled bit and cksum
            self.scrambled_cksum = scrambled_cksum(self.solution, 
                                                   self.width, 
                                                   self.height)
            self.solution_state = SolutionState.Locked
            self.solution = scramble_solution(self.solution, 
                                              self.width, 
                                              self.height, 
                                              key)
  

    #--------------- Checksum Stuff

    def header_cksum(self, cksum=0):
        """Return checksum of header section."""

        return data_cksum(
                struct.pack(HEADER_CKSUM_FORMAT, 
                            self.width, 
                            self.height, 
                            len(self.clues), 
                            self.puzzletype, 
                            self.solution_state), 
                cksum)
    

    def text_cksum(self, cksum=0):
        """Checksum of textual parts of puzzle."""

        # For the checksum to work these fields must be added in order with
        # null termination, followed by all non-empty clues without null
        # termination, followed by notes (but only for version 1.3)

        if self.title:
            cksum = data_cksum(self.title + '\0', cksum)
        if self.author:
            cksum = data_cksum(self.author + '\0', cksum)
        if self.copyright:
            cksum = data_cksum(self.copyright + '\0', cksum)
    
        for clue in self.clues:
            if clue:
                cksum = data_cksum(clue, cksum)
    
        # Notes included in global cksum only in v1.3 of format
        if self.version == '1.3' and self.notes:
            cksum = data_cksum(self.notes + '\0', cksum)
        
        return cksum

        
    def global_cksum(self):
        """Return global checksum of puzzle."""

        cksum = self.header_cksum()
        cksum = data_cksum(self.solution, cksum)
        cksum = data_cksum(self.fill, cksum)
        cksum = self.text_cksum(cksum)
        # Extensions do not seem to be included in global cksum

        return cksum
  

    def magic_cksum(self):
        """Return masked magic checksum."""

        cksums = [
            self.header_cksum(),
            data_cksum(self.solution),
            data_cksum(self.fill),
            self.text_cksum()
        ]
    
        cksum_magic = 0
        for (i, cksum) in enumerate(reversed(cksums)):
            cksum_magic <<= 8
            cksum_magic |= (MASKSTRING[len(cksums)-i-1] ^ (cksum & 0x00ff))
            cksum_magic |= (MASKSTRING[len(cksums)-i-1+4] ^ (cksum >> 8)) << 32
    
        return cksum_magic

        
class PuzzleBuffer:
    """Buffer for dealing with puzzle raw data.

    Wraps a data buffer ('' or []) and provides .puz-specific methods for
    reading and writing data.
    """

    def __init__(self, data=None, enc='ISO-8859-1'):
        self.data = data or []
        self.enc = enc
        self.pos = 0
  

    def can_read(self, nbytes=1):
        """Can we read nbytes from our current position?"""

        return self.pos + nbytes <= len(self.data)
  

    def read(self, nbytes):
        """Read nbytes and return as bytes."""

        start = self.pos
        self.pos += nbytes
        return self.data[start:self.pos]


    def read_to_end(self):
        """Read until end and return as bytes."""

        start = self.pos
        self.pos = len(self.data)
        return self.data[start:self.pos]
  

    def read_string(self):
        """Read null-terminated string and return as string."""

        start = self.pos
        self.seek_to(b'\0', 1) # read past
        return self.data[start:self.pos-1].decode(self.enc)


    def seek_to(self, s, offset=0):
        """Seek to bytes <s> in buffer + offset.

        If s is not found, seek to end.

        Returns True on success or False on failure.
        """

        try:
            self.pos = self.data.index(s, self.pos) + offset
            return True
        except ValueError:
            # s not found, advance to end
            self.pos = len(self.data)
            return False
    

    def write(self, s):
        """Write bytes <s> to buffer."""

        self.data.append(s)
    

    def write_string(self, s):
        """Write string <s> to buffer as bytes + NULL terminator."""

        #s = s or ''   WJB when would need this?
        self.data.append(s.encode(self.enc) + b'\0')
    

    def pack(self, sformat, *values):
        """Pack a struct using format & values and append to buffer."""

        self.data.append(struct.pack(sformat, *values))
  

    def can_unpack(self, sformat):
        """Can we read enough bytes for struct of this format?"""

        return self.can_read(struct.calcsize(sformat))
  

    def unpack(self, sformat):
        """Read struct with format at current position and return."""

        start = self.pos

        try:
            res = struct.unpack_from(sformat, self.data, self.pos)
            self.pos += struct.calcsize(sformat)
            return res

        except struct.error:
            raise PuzzleFormatError(
                    'Could not unpack values at {} for format {}'.format(
                        start, format))
        

    def as_bytes(self):
        """Return buffer as bytes."""

        return b''.join(self.data)



class DefaultClueNumbering:
    """Utility to convert raw grid and raw clue list to numbered clues.

    Set across and down to lists of dictionaries for each across/down clue:
      num: human number for clue (ie, 3 in 3D)
      clue: clue text
      cell: 0-based index for cell in grid
      len: lenght of word
    """

    def __init__(self, grid, clues, width, height):
        self.grid = grid
        self.clues = clues
        self.width = width
        self.height = height

        self.across = []
        self.down = []

        # Index into list of clues found in puzzle data
        clueidx = 0

        # Human-facing clue number (ie, clue number 1 might be for 1A and 1D)
        cluenum = 1

        # Loop over each cell in grid. If word starts here, get clue and
        # add to list of across/down clue, as appropriate.

        for i in range(0, len(grid)):

            if is_blacksquare(grid[i]):
                continue

            found = False

            # Are we at left edge of puzzle or word?
            if ( (self._col(i) == 0 or is_blacksquare(grid[i-1])) 
                    and self._len_across(i) > 1 ):
                self.across.append( {'num': cluenum,
                                     'clue': clues[clueidx], 
                                     'cell': i, 
                                     'len': self._len_across(i) } )
                clueidx += 1
                found = True


            # Are we at top row of puzzle or word?
            if ( (self._row(i) == 0 or is_blacksquare(grid[i-width])) 
                    and self._len_down(i) > 1 ):
                self.down.append( {'num': cluenum, 
                                   'clue': clues[clueidx], 
                                   'cell': i, 
                                   'len': self._len_down(i) } )
                clueidx += 1
                found = True

            # If we found any clues here, bump up the human clue number for
            # the next time around.

            if found:
                cluenum += 1


    def _col(self, i):
        # Column for this index (0-based)
        return i % self.width
    
    def _row(self, i):
        # Row for this index (0-based)
        return i // self.width

    def _len_across(self, i):
        # Length of across word at index i
        for c in range(0, self.width-self._col(i)):
            if is_blacksquare(self.grid[i+c]):
                return c    
        return c + 1
    
    def _len_down(self, i):
        # Length of down word at index i
        for c in range(0, self.height - self._row(i)):
            if is_blacksquare(self.grid[i+c*self.width]):
                return c
        return c + 1



class Rebus:
    """Utility to manage rebus information.
    
    Rebuses are controlled by three extensions to a .puz file:
       Rebus (GRBS): grid of puzzle; 1=0 non-rebus square; i+1 is key for i in
                     rebus solutions map
       RebusSolutions (RTBL): map of rebus solution entires (eg,
                              0:HEART; 1:DIAMOND, etc)
       RebusFill (RUSR): User's rebus entries
    """

    def __init__(self, puzzle):
        self.puzzle = puzzle
        #self.table = to_byte_array(self.puzzle.extensions.get(Extensions.Rebus, b''))
        self.table = self.puzzle.extensions.get(Extensions.Rebus, b'')


        def _to_list(s):
            # Turns A:1;B:2;C:3  -->  [ ('A',1), ('B',2), ('C', 3) ]
            return [ p.split(b':') for p in s.split(b';') if b':' in p ]

        raw_solutions = self.puzzle.extensions.get(Extensions.RebusSolutions, b'')
        self.solutions = { int(p[0]): p[1] for p in _to_list(raw_solutions) }

        raw_fill = self.puzzle.extensions.get(Extensions.RebusFill, b'')
        self.fill = { int(p[0]): p[1] for p in _to_list(raw_fill) }
    

    def has_rebus(self):
        """Does puzzle have a rebus section?"""

        return Extensions.Rebus in self.puzzle.extensions
    

    def is_rebus_square(self, i):
        """Is this square a rebus square?"""

        return bool(self.table[i])
        

    def save(self):
        """Save rebus information back to extensions dictionary."""

        def _to_bytes(d):
            # [ (1,'A'), (2,'B') ]  -->  b'1:A;2:B' 
            return b';'.join( str(k).encode() + b':' + v for k, v in d.items() )

        if self.has_rebus():
            self.puzzle.extensions[Extensions.Rebus] = self.table

            self.puzzle.extensions[Extensions.RebusSolutions] = _to_bytes(self.solutions)
            self.puzzle.extensions[Extensions.RebusFill] = _to_bytes(self.fill)



class Timer:
    """Helper to manager timer."""

    def __init__(self, puzzle):
        self.puzzle = puzzle
        self.elapsed_sec = 0
        self.paused = True

        self.timer = self.puzzle.extensions.get(Extensions.Timer, b'')

        if self.timer:
            print(self.timer)
            elapsed_sec, paused = self.timer.split(b',')
            self.elapsed_sec = int(elapsed_sec)
            self.paused = bool(int(paused))


    def has_timer(self):
        """Is there timer data?"""

        return bool(self.timer)

   
    def save(self):
        """Save timer back to puzzle extensions dictionary."""

        if self.has_timer():
           self.puzzle.extensions[Extensions.Timer] = self.timer



class Markup:
    """Utility to manage markup.
    """

    def __init__(self, puzzle):
        self.puzzle = puzzle
        self.markup = self.puzzle.extensions.get(Extensions.Markup, b'')
        #self.markup = to_byte_array(self.puzzle.extensions.get(Extensions.Markup, b''))
    

    def has_markup(self):
        """"Is there any markup in the puzzle?"""

        return any(bool(b) for b in self.markup)
    

    def save(self):
        """Save markup back to puzzle extensions dictionary."""
        if self.has_markup():
            #self.puzzle.extensions[Extensions.Markup] = from_byte_array(self.markup)
            self.puzzle.extensions[Extensions.Markup] = self.markup



######################################################################################
# Complex stuff below for checksums and scrambling. Reader beware.


def data_cksum(data, cksum=0):
    if type(data) == type(""):
        data = data.encode()
    #print (data, type(data))
    for b in list(data):
        # right-shift one with wrap-around
        lowbit = (cksum & 0x0001)
        cksum = (cksum >> 1)
        if lowbit: cksum = (cksum | 0x8000)
    
        # then add in the data and clear any carried bit past 16
        #import pdb; pdb.set_trace()
        cksum = (cksum + b) & 0xffff

    return cksum

def scramble_solution(solution, 
                      width, 
                      height, 
                      key):
    sq = square(solution, width, height)
    return square(restore(sq, scramble_string(sq.replace(BLACKSQUARE, ''), key)), 
                  height, 
                  width)

def scramble_string(s, key):
    """
    s is the puzzle's solution in column-major order, omitting black squares:    
    i.e. if the puzzle is:
        C A T
        # # A
        # # R
    solution is CATAR    


    Key is a 4-digit number in the range 1000 <= key <= 9999

    """
    key = key_digits(key)
    for k in key: # foreach digit in the key
        s = shift(s, key)  # xform each char by each digit in the key in sequence
        s = s[k:] + s[:k]  # cut the sequence around the key digit
        s = shuffle(s)     # do a 1:1 shuffle of the 'deck'

    return s

def unscramble_solution(scrambled, width, height, key):
    # width and height are reversed here
    sq = square(scrambled, width, height)
    return square(restore(sq, unscramble_string(sq.replace(BLACKSQUARE, ''), key)), 
                  height, 
                  width)
    

def unscramble_string(s, key):
    key = key_digits(key)
    l = len(s)
    for k in key[::-1]:
        s = unshuffle(s)
        s = s[l-k:] + s[:l-k]
        s = unshift(s, key)

    return s


def scrambled_cksum(scrambled, width, height):
    return data_cksum(square(scrambled, width, height).replace(BLACKSQUARE, ''))


def key_digits(key):
    return [int(c) for c in str(key).zfill(4)]


def square(data, w, h):
    aa = [data[i:i+w] for i in range(0, len(data), w)]
    return ''.join([''.join([aa[r][c] for r in range(0, h)]) for c in range(0, w)])


def shift(s, key):
    atoz = string.ascii_uppercase
    return ''.join(atoz[(atoz.index(c) + key[i % len(key)]) % len(atoz)] for i, c in enumerate(s))


def unshift(s, key):
    return shift(s, [-k for k in key])


def shuffle(s):
    mid = len(s) // 2
    return ''.join(reduce(operator.add, list(zip(s[mid:], s[:mid])))) + (s[-1] if len(s) % 2 else '')


def unshuffle(s):
    return s[1::2] + s[::2]


def restore(s, t):
    """
    s is the source string, it can contain '.'
    t is the target, it's smaller than s by the number of '.'s in s
    each char in s is replaced by the corresponding char in t, jumping over '.'s in s

    >>> restore('ABC.DEF', 'XYZABC')
    'XYZ.ABC'
    """

    t = (c for c in t)
    return ''.join(next(t) if not is_blacksquare(c) else c for c in s)

