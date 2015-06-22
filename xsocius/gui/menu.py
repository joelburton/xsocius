"""Menu bars."""

import wx

from xsocius.utils import NAME
from xsocius.gui.utils import get_icon
import collections

class MenuBar(wx.MenuBar):
    """wx.MenuBar subclass that can create menus from data structure."""
    
    # This is a generic wx utility and unrelated to Xoscius per se--it allows
    # you to create menus by creating a subclass with a particular data 
    # structure.  The classes for Xsocius for this are at the end of this file.


    # 2to3: XXX workaround for API change in Phoenix; likely to be switched back
    #def FindItemById(self, *args, **kw):
    #    return self.FindItembyId(*args, **kw)


    def _menu_data(self, app, window):
        """Returns menu dict."""

        # Override this in your subclasses with the data structure for
        # your menu.

        raise NotImplementedError()


    def add_menu_item(self, menu, window, idstr, label, accel, bind, kind=0):
        """Add menu item to menu."""

        # If there is a wx.ID_LIKE_OURS, use it; else create one
        # This allows us to use common classes like ID_COPY, ID_PASTE,
        # while also creating new ones.
        itemid = getattr(wx, 'ID_' + idstr, wx.NewId())
        setattr(window, 'ID_' + idstr, itemid)

        # Fix up accel string and append to label
        accel = accel.replace('C-', 'Ctrl-')
        accel = accel.replace('S-', 'Shift-')
        accel = accel.replace('A-', 'Alt-')
        if accel:
            label = label + '\t' + accel

        # Update placeholder for program name
        label = label.replace('NAME', NAME)

        # Create menu item
        item = menu.Append(itemid, label, kind=kind)

        # Handle check items
        if kind == wx.ITEM_CHECK:
            menu.Check(itemid, True)

        window.Bind(wx.EVT_MENU, bind, item)


    def add_menu_items(self, menu, window, items):
        """Loop over items and add them."""

        if isinstance(items, collections.Callable):
            # We're a special menu/submenu: instead of list of kids, a callable
            #
            # Used for things like "Recent Files" sections; the submenu
            # for Recent Files is created, then a callable method name is
            # put in instead of a list. This method takes care of populating
            # the submenu dynamically.
            items(menu, window)
            return

        for item in items:

            if item == "--":
                menu.AppendSeparator()

            elif type(item) == type(tuple()) and len(item) > 2:
                # Standard menu item (id, name, accel, binding)
                self.add_menu_item(menu, window, *item)

            else:
                # A submenu: name, list/callable for children
                # We call this method with child list/callable to populate it
                menuname, subitems = item
                submenu = wx.Menu()
                self.add_menu_items(submenu, window, subitems)
                menu.Append(wx.ID_ANY, menuname, submenu)


    def make_menu_bar(self, app, window):
        """Make menubar from structured list and return it."""

        for menuname, items in self._menu_data(app, window):
            menu = wx.Menu()
            self.add_menu_items(menu, window, items)
            self.Append(menu, menuname)


    def __init__(self, window):
        wx.MenuBar.__init__(self)
        app = wx.GetApp()

        # Should make "Windows" menu appear automatically on OSX, but
        # doesn't work in wx2.9.
        # XXX 2to3: not present in Phoenix
        #wx.MenuBar.SetAutoWindowMenu(True)

        self.make_menu_bar(app, window)

        # Unsure what this is supposed to do.
        # but doesn't seem to have any effect, so commented out.
        # self.bar.MacSetCommonMenuBar(self.bar)


#---------------------------- APP SPECIFIC STUFF


def _add_web_sources(menu, window):
    """Add web openers to menu."""

    app = wx.GetApp()
    for i, opener in enumerate(app.config.getWebOpeners()):
        item = menu.Append(wx.ID_ANY, opener['name'])
        item.SetBitmap(wx.Bitmap(get_icon(opener["icon"])))
        window.Bind(wx.EVT_MENU, 
                lambda event, idx=i: app.OnOpenWeb(event, idx), 
                item)


def _add_recent_files(menu, window):
    """Add recent file menu to menu."""

    app = wx.GetApp()
    window.RecentMenu = menu
    app.config.filehistory.UseMenu(menu)
    app.config.filehistory.AddFilesToMenu(menu)
    window.Bind(wx.EVT_MENU_RANGE, app.OnFileHistory, id=wx.ID_FILE1, id2=wx.ID_FILE9)


class BrowserMenuBar(MenuBar):
    """Menu bar used for browser window."""

    def _menu_data(self, app, window):
        """Return structured list of menu data."""

        # Item format is 'ID', 'Label', 'Accels', bind, style (opt)

        # Aliases to keep structure more readable
        a = app
        w = window

        return [
      ('&File', [
        ('CLOSE',         'Close',                  'C-W',    w.OnClose), 
        ('EXIT',          'E&xit',                  'C-Q',    w.OnQuit), ]),
      ('&Help', [
        ('HELP',          'NAME &Help',             '',       a.OnHelp),
        ('BUGREPORT',     'NAME Bug Report',        '',       a.OnBugReport),
        ('ABOUT',         'About NAME',             '',       a.OnAbout), ]),
        ]


class DummyMenuBar(MenuBar):
    """Menu bar used for dummy window."""

    def _menu_data(self, app, window):
        """Return structured list of menu data."""

        # Item format is 'ID', 'Label', 'Accels', bind, style (opt)

        # Aliases to keep structure more readable
        a = app
        w = window

        return [

      ('&File', [
        (                 'Open &Web Puzzle',                 _add_web_sources),
        ('WEB_CHOOSER',   'Web Puzzle Chooser...',  'A-C-O',  a.OnWebChooser),
         '--',
        ('OPEN',          'Open File Puzzle...',    'C-O',    a.OnOpen),
        ('OPEN_UNSOLVED', 'Open as Unsolved...',    'S-C-O',  a.OnOpenUnsolved),
        (                 'Open &Recent',                     _add_recent_files),
         '--',
        ('JOIN',          '&Join Shared Puzzle...', 'C-J',    w.OnJoin),
         '--',
        ('CLOSE',         'Close',                  'C-W',    w.OnClose),
        ('EXIT',          'E&xit',                  'C-Q',    a.OnQuit),
        ('PREFERENCES',   'P&references...',        'C-,',    a.OnPrefs), ]),

      ('&Help', [
        ('HELP',          'NAME &Help',             '',       a.OnHelp),
        ('BUGREPORT',     'NAME Bug Report',        '',       a.OnBugReport),
        ('ABOUT',         'About NAME',             '',       a.OnAbout), ]),
        ]


class PuzzleMenuBar(MenuBar):
    """Menu bar used for puzzle windows."""

    def _menu_data(self, app, window):
        """Return structured list of menu data."""

        # Item format is 'ID', 'Label', 'Accels', bind, style (opt)

        # Aliases to keep structure more readable
        a = app
        w = window

        return [

('&File', [

  (                 'Open &Web Puzzle',                 _add_web_sources),
  ('WEB_CHOOSER',   'Web Puzzle Chooser...',  'A-C-O',  a.OnWebChooser),
   '--',
  ('OPEN',          'Open File Puzzle...',    'C-O',    a.OnOpen),
  ('OPEN_UNSOLVED', 'Open as Unsolved...',    'S-C-O',  a.OnOpenUnsolved),
  (                 'Open &Recent',                     _add_recent_files),
   '--',
  ('SHARE',         'Share Puzzle...',        'A-C-J',  w.OnShare),
  ('JOIN',          '&Join Shared Puzzle...', 'C-J',    w.OnJoin),
  ('REINVITE',      'Resend Invitations...',  'C-S-J',  w.OnResendInvitation),
  ('DISCONNECT',    'Disconnect',             'C-A-S-J',w.OnDisconnect),
   '--',
  ('CLOSE',         'Close',                  'C-W',    w.OnClose),
  ('SAVE',          '&Save',                  'C-S',    w.OnSave),
  ('SAVEAS',        'Save &As...',            'C-S-S',  w.OnSaveAs),
  ('REVERT',        'Revert to Saved',        '',       w.OnRevert),
   '--',
  ('PRINT_SETUP',   'Print Setup...',         'S-C-P',  w.OnPrintSetup),
  ('PRINT_PREVIEW', 'Print Preview',          'A-C-P',  w.OnPrintPreview),
  ('PRINT',         '&Print...',              'C-P',    w.OnPrint),
  ('EXIT',          'E&xit',                  'C-Q',    a.OnQuit),
  ('PREFERENCES',   'P&references...',        'C-,',    a.OnPrefs), ]),

('&Edit', [

  ('STARTOVER',     'Start Over',             'A-C-Back', w.OnStartOver),
   '--',
  ('ENTER_REBUS',   'Enter Special Answer...','A-C-M',  w.OnSpecialAnswer),
   '--',
  ('TOGGLE_PEN',    'Use Pencil',             'C-E',    w.OnTogglePen),
   '--',
  ('UNDO',          'Undo',                   'C-Z',    w.OnUndo),
  ('REDO',          'Redo',                   'S-C-Z',  w.OnRedo),
   '--',
  ('CUT',           'Cut Word',               'C-X',    w.OnCut),
  ('COPY',          'Copy Word',              'C-C',    w.OnCopy),
  ('PASTE',         'Paste Word',             'C-V',    w.OnPaste),
  ('CLEAR',         'Clear Word',             'C-Back', w.OnClear), ]),

('&Puzzle', [

  ('Check', [
     ('CHECK_LETTER',     'Current Letter',   'C-K',    w.OnCheckLetter),
     ('CHECK_WORD',       'Current Word',     'S-C-K',  w.OnCheckWord),
     ('CHECK_PUZZLE',     'Entire Puzzle',    'A-C-K',  w.OnCheckPuzzle), ]),

  ('Reveal', [
     ('REVEAL_LETTER',    'Current Letter',   'C-R',    w.OnRevealLetter),
     ('REVEAL_WORD',      'Current Word',     'S-C-R',  w.OnRevealWord),
     ('REVEAL_PUZZLE',    'Entire Puzzle',    'A-C-R',  w.OnRevealPuzzle),
      "--",
     ('REVEAL_WRONG',     'Incorrect Letters','C-A-S-R',w.OnRevealWrong), ]),

   '--',
  ('TIMER_TOGGLE',        'Start Timer',      'C-T',    w.OnTimerToggle),
  ('TIMER_CLEAR',         'Reset Timer',      '',       w.OnTimeClear),
   '--',
  ('UNLOCK',        'Unlock Puzzle',          '',       w.OnUnlock),
  ('LOCK',          'Lock Puzzle',            '',       w.OnLock),
  # '--',
  ('HIGHLIGHT',     'Highlight Answer',       'C-I',    w.OnHighlight),
  ('HIGHLIGHT_CLR', 'Clear Highlights',       'C-A-I',  w.OnHighlightClr),
   '--',
  ('SHOW_NOTE',     'Show Note',              '',       w.OnShowNote),

  ('Clues', [
     ('SHOW_CLUES',      'Show Clues Sidebar','',       w.OnShowClues, 
                                                          wx.ITEM_CHECK),
     ('CLUES_BIGGER',    'Increase Font Size','C-+', w.OnCluesFontBigger),
     ('CLUES_SMALLER',   'Decrease Font Size','C--', w.OnCluesFontSmaller), ]),

   '--',
  ('ONEACROSS',     'OneAcross.com Lookup',   'C-L',    w.OnOneAcross),
  ('GOOGLE',        'Google.com Lookup',      'C-S-L',  w.OnGoogle), ]),

('&Window', [
  ('FULLSCREEN',    'Fullscreen',             'C-A-F',  w.OnFullScreen), ]),

('&Help', [

  ('HELP',          'NAME &Help',             '',       a.OnHelp),
  ('BUGREPORT',     'NAME Bug Report',        '',       a.OnBugReport),
  ('ABOUT',         'About NAME',             '',       a.OnAbout), ]),

          ]
