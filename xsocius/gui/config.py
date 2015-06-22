"""Application configuration."""

import logging

import os
import wx
from xsocius.utils import NAME

WEB_SOURCES = [

    {'id': 'sys:nytimes',
     'name': 'New York Times Classic',
     'url': 'http://www.nytimes.com/specials/puzzles/classic.puz',
     'days': '1',
     'desc': 'Free puzzle from the New York Times archives.',
     'enabled': True,
     'icon': 'nytimes.gif'},

    {'id': 'sys:chicagoreader',
     'name': 'Chicago Reader',
     'url': 'http://herbach.dnsalias.com/Tausig/vv%y%m%d.puz',
     'days': '5',
     'desc': '',
     'enabled': True,
     'icon': 'chicagoreader.gif'},

    {'id': 'sys:chronicle',
     'name': 'Chronicle of Higher Education',
     'url': 'http://chronicle.com/items/biz/puzzles/%Y%m%d.puz',
     'days': '5',
     'desc': 'Large weekly puzzle.',
     'enabled': True,
     'icon': 'chronicle.gif'},

    {'id': 'sys:wallstreet',
     'name': 'Wall Street Journal',
     'url': 'http://mazerlm.home.comcast.net/~mazerlm/wsj%y%m%d.puz',
     'days': '5',
     'enabled': True,
     'desc': '',
     'icon': 'wallstreet.gif'},

    {'id': 'sys:nytimesprem',
     'name': 'New York Times Premium',
     'url': 'http://www.nytimes.com/premium/xword/%Y/%m/%d/%b%d%y.puz',
     'days': '1234567',
     'desc': 'Requires paid subscription; see help for details.',
     'enabled': True,
     'icon': 'nytimes.gif'},

    {'id': 'sys:nytimesprem1',
     'name': 'New York Times Premium (Monday)',
     'url': 'http://select.nytimes.com/premium/xword/%b%d%y.puz',
     'days': '1',
     'desc': 'Requires paid subscription; see help for details.',
     'enabled': False,
     'icon': 'nytimes.gif'},

    {'id': 'sys:nytimesprem2',
     'name': 'New York Times Premium (Tuesday)',
     'url': 'http://select.nytimes.com/premium/xword/%b%d%y.puz',
     'days': '2',
     'desc': 'Requires paid subscription; see help for details.',
     'enabled': False,
     'icon': 'nytimes.gif'},

    {'id': 'sys:nytimesprem3',
     'name': 'New York Times Premium (Wednesday)',
     'url': 'http://select.nytimes.com/premium/xword/%b%d%y.puz',
     'days': '3',
     'desc': 'Requires paid subscription; see help for details.',
     'enabled': False,
     'icon': 'nytimes.gif'},

    {'id': 'sys:nytimesprem4',
     'name': 'New York Times Premium (Thursday)',
     'url': 'http://select.nytimes.com/premium/xword/%b%d%y.puz',
     'days': '4',
     'desc': 'Requires paid subscription; see help for details.',
     'enabled': False,
     'icon': 'nytimes.gif'},

    {'id': 'sys:nytimesprem5',
     'name': 'New York Times Premium (Friday)',
     'url': 'http://select.nytimes.com/premium/xword/%b%d%y.puz',
     'days': '5',
     'desc': 'Requires paid subscription; see help for details.',
     'enabled': False,
     'icon': 'nytimes.gif'},

    {'id': 'sys:nytimesprem6',
     'name': 'New York Times Premium (Saturday)',
     'url': 'http://select.nytimes.com/premium/xword/%b%d%y.puz',
     'days': '6',
     'desc': 'Requires paid subscription; see help for details.',
     'enabled': False,
     'icon': 'nytimes.gif'},

    {'id': 'sys:nytimesprem7',
     'name': 'New York Times Premium (Sunday)',
     'url': 'http://select.nytimes.com/premium/xword/%b%d%y.puz',
     'days': '7',
     'desc': 'Requires paid subscription; see help for details.',
     'enabled': False,
     'icon': 'nytimes.gif'},

    {'id': 'sys:jonesin',
     'name': "Jonesin' Crosswords",
     'url': 'http://herbach.dnsalias.com/Jonesin/jz%y%m%d.puz',
     'days': '4',
     'desc': '',
     'enabled': True,
     'icon': None, },

    {'id': 'sys:iswear',
     'name': 'I Swear Crosswords',
     'url': 'http://wij.theworld.com/puzzles/dailyrecord/DR%y%m%d.puz',
     'days': '5',
     'desc': '',
     'enabled': True,
     'icon': None, },

]


class XsociusConfig(object):
    """Configuration object.

       Uses wx.Config for underlying storage. Storage application preferences,
       along with file history.
    """

    _PROPERTIES = [
        # name                 section default    descrip
        ("openmethod", "ui", "none", "What to do on startup"),
        ("reopen", "ui", True, "Re-open puzzles on start?"),
        ("note_on_open", "ui", True, "Show puzzle note on open?"),
        ("flag_graphic", "ui", True, "Use graphic flags?"),
        ("flag_letter", "ui", True, "Use letter flags?"),
        ("letter_error_color", "ui", "#991111", "Color of error letters"),
        ("letter_checked_color", "ui", "#116611", "Color of checked letters"),
        ("letter_cheat_color", "ui", "#111199", "Color of cheated letters"),
        ("graphic_error_color", "ui", "#BB3333", "Color of error graphics"),
        ("graphic_checked_color", "ui", "#33AA33", "Color of checked graphics"),
        ("graphic_cheat_color", "ui", "#3333FF", "Color of cheated graphics"),
        ("internal_browser", "ui", True, "Use internal browser?"),
        ("show_clues", "ui", True, "Show clue lists by default"),
        ("skip_filled", "ui", False, "Skip filled-in grid letters"),
        ("end_at_word", "ui", True, "End at word when typing"),
        ("timer_autostart", "ui", False, "Auto-start timer"),
        ("check_upgrades", "ui", True, "Check for upgrades?"),
        ("show_tips", "ui", True, "Show tips-of-day on startup"),
        ("tips_index", "ui", 0, "Show clue #"),
        ("grey_filled_clues", "ui", True, "Grey filled-in clues?"),
        ("flash_correct", "ui", False, "Flash words when completed?"),

        ("no_cheats", "tourn", False, "Disable checking/cheating"),
        ("no_autowin", "tourn", False, "Disable auto-display on win"),
        ("no_timerpause", "tourn", False, "Disable pausing of timer"),
        ("no_unlock", "tourn", False, "Disable unlocking puzzle"),
        ("no_oneacross", "tourn", False, "Disable oneacross.com"),

        ("server", "sharing", "talk.google.com", "Default server"),
        ("username", "sharing", "you@gmail.com", "Default username"),
        ("password", "sharing", "", "Default password"),
        ("skip_conn_dlg", "sharing", False, "Skip dialog & use settings?"),
        ("invisible", "sharing", False, "Stay invisible"),
        ("autoend_im", "sharing", True, "Focus to grid after send IM"),
        ("im_sound", "sharing", True, "Play sound when reeiving IM"),
        ("im_flash", "sharing", True, "Flash window on receive IM"),
    ]

    filehistory = None

    def __init__(self):

        if wx.Platform == '__WXGTK__':
            # Otherwise, Linux tries to use same name for
            # storage dir and prefs file.
            self.config = wx.Config("%s-prefs" % NAME)  # .Get()
        else:
            self.config = wx.Config().Get()

        if not self.config.Exists("/recent"):
            self._create_initial()
        else:
            self._update_existing()

        self._load_file_history()

        # Let's call this for the side-effect of creating the storage dir,
        # if not there.
        self.getCrosswordsDir()

        self._add_properties()

    def _create_initial(self):
        """Create configuration file.

           Config doesn't exist (first time running app as this user?), so
           create it with barebones defaults.
        """

        _prop = self.config.Write
        _bool = self.config.WriteBool
        _int = self.config.WriteInt

        logging.info("Creating initial config file (create_initial)")
        self.config.SetPath("/recent")
        _int("num", 9)
        self.setWebOpeners(WEB_SOURCES)

        # Set default for properties
        for prop, section, default, descrip in self._PROPERTIES:
            key = "/%s/%s" % (section, prop)
            if type(default) == type(0):
                _int(key, default)
            elif type(default) == type(True):
                _bool(key, default)
            elif type(default) == type(""):
                _prop(key, default)
            else:
                raise Exception("Wrong prop type")

        self.config.Flush()

    def _update_existing(self):
        """Update existing config file."""

        openers = self.getWebOpeners(include_disabled=True)
        enabled = {o['id']: o['enabled'] for o in openers}
        self.setWebOpeners(WEB_SOURCES, enabled)

    def getCrosswordsDir(self):
        """Directory for storage of crosswords."""

        standard_paths = wx.StandardPaths.Get()
        directory = standard_paths.GetUserLocalDataDir() + "/Crosswords"

        if not os.access(directory, os.W_OK):
            try:
                os.makedirs(directory)
            except OSError as e:
                logging.error("Can't create %s: %s", directory, e)
                dlg = wx.MessageDialog(None,
                                       "Cannot create our crossword directory"
                                       " at\n%s.\n\nPlease fix." % directory,
                                       "Critical Error", wx.OK | wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
                raise Exception()

        return directory

    def getSupportDir(self):
        """Directory for support files."""

        standard_paths = wx.StandardPaths.Get()
        directory = standard_paths.GetUserLocalDataDir()

        if not os.access(directory, os.W_OK):
            try:
                os.makedirs(directory)
            except OSError as e:
                logging.error("Can't create %s: %s", directory, e)
                dlg = wx.MessageDialog(None,
                                       "Cannot create our application support directory"
                                       " at\n%s.\n\nPlease fix." % directory,
                                       "Critical Error", wx.OK | wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
                raise Exception()

        return directory

    # ---- File History

    def _load_file_history(self):
        """Load file history.

           Config file holds number of maximum files to track and files.
        """

        self.config.SetPath("/recent")
        self.filehistory = wx.FileHistory(maxFiles=self.config.ReadInt("num"))
        self.filehistory.Load(self.config)

    def addRecentFile(self, path):
        """Add new file to recent-files list."""

        self.config.SetPath("/recent")
        self.filehistory.AddFileToHistory(path)
        self.filehistory.Save(self.config)
        self.config.Flush()

    # ----- Web Openers


    def getWebOpeners(self, include_disabled=False):
        """Return web openers as list of dicts."""

        openers = []
        self.config.SetPath("/web")
        more, id_, next_ = self.config.GetFirstGroup()
        if not id_: return []
        while True:
            enabled = self.config.ReadBool("%s/enabled" % id_)
            if enabled or include_disabled:
                name = self.config.Read("%s/name" % id_)
                url = self.config.Read("%s/url" % id_)
                icon = self.config.Read("%s/icon" % id_)
                days = self.config.Read("%s/days" % id_)
                desc = self.config.Read("%s/desc" % id_)
                openers.append({'id': id_, 'name': name, 'url': url, 'icon': icon,
                                'days': days, 'enabled': enabled, 'desc': desc})
            more, id_, next_ = self.config.GetNextGroup(next_)
            if not more:
                break
        return sorted(openers, key=lambda x: x['id'])

    def setWebOpeners(self, openers, curr_enabled=None):
        """Save web openers from list of dicts.
        
           Can be called during upgrade, in which case it's
           also given a dict of {'id':puzzid, 'enabled':currstate}
           representing the current state; these are kept.
        """

        _prop = self.config.Write
        _bool = self.config.WriteBool
        _int = self.config.WriteInt
        self.config.DeleteGroup("/web")
        for o in openers:
            self.config.SetPath("/web/%s" % o['id'])
            _prop("name", o['name'])
            _prop("url", o['url'])
            _prop("days", o['days'])
            _prop("desc", o['desc'])
            if curr_enabled:
                # We're upgrading, keep current enabled state
                _bool("enabled", curr_enabled.get(o['id'], o['enabled']))
            else:
                # We're saving prefs, use choice made by user
                _bool("enabled", o['enabled'])
            _prop("icon", o['icon'] or 'generic.gif')
        self.config.Flush()

    # ---- Window Persistence

    def persistWindows(self, paths):
        """Saves list of open puzzles."""

        logging.debug("Persisting: %s", paths)
        self.config.DeleteGroup("/persist")
        for i, path in enumerate(paths):
            self.config.Write("/persist/%s" % i, path)
            self.config.Flush()

    def unpersistWindows(self):
        """Return list of windows to open."""

        logging.debug("Called unpersistWindows.")
        paths = []
        self.config.SetPath("/persist")
        more, value, idx = self.config.GetFirstEntry()
        if not value:
            return []
        while True:
            paths.append(self.config.Read("/persist/%s" % value))
            more, value, idx = self.config.GetNextEntry(idx)
            if not more:
                break
        logging.debug("Unpersisting: %s", paths)
        return paths

    # ---- General Preferences

    def _read(self, key):
        val = self.config.Read(key)
        logging.debug("reading %s from %s",
                      val if not 'password' in key else '***', key)
        return val

    def _write(self, key, val):
        logging.debug("writing %s to %s", key,
                      val if not 'password' in key else '***')
        self.config.Write(key, val)
        self.config.Flush()

    def _readint(self, key):
        val = self.config.ReadInt(key)
        logging.debug("reading %s from %s", val, key)
        return val

    def _writeint(self, key, val):
        logging.debug("writing %s to %s", key, val)
        self.config.WriteInt(key, val)
        self.config.Flush()

    def _readbool(self, key):
        val = self.config.ReadBool(key)
        logging.debug("reading %s from %s", val, key)
        return val

    def _writebool(self, key, val):
        logging.debug("writing %s to %s", key, val)
        self.config.WriteBool(key, val)
        self.config.Flush()

    @classmethod
    def _make_string_prop(cls, name, key, descrip):
        setattr(cls, name,
                property(lambda s: s._read(key),
                         lambda s, v: s._write(key, v),
                         None, descrip))

    @classmethod
    def _make_int_prop(cls, name, key, descrip):
        setattr(cls, name,
                property(lambda s: s._readint(key),
                         lambda s, v: s._writeint(key, v),
                         None, descrip))

    @classmethod
    def _make_bool_prop(cls, name, key, descrip):
        setattr(cls, name,
                property(lambda s: s._readbool(key),
                         lambda s, v: s._writebool(key, v),
                         None, descrip))

    def _add_properties(self):
        """Add getter/setter properties to class."""

        for name, sect, default, descrip in self._PROPERTIES:
            key = "/%s/%s" % (sect, name)
            setattr(self, name + "_default", default)

            # String properties
            if type(default) == type(""):
                self._make_string_prop(name, key, descrip)
                if not self.config.Exists(key):
                    logging.debug("Adding new property %s=%s", key, default)
                    self._write(key, default)

            # Int properties
            elif type(default) == type(0):
                self._make_int_prop(name, key, descrip)
                if not self.config.Exists(key):
                    logging.debug("Adding new property %s=%s", key, default)
                    self._writeint(key, default)

            # Boolean properties
            elif type(default) == type(True):
                self._make_bool_prop(name, key, descrip)
                if not self.config.Exists(key):
                    logging.debug("Adding new property %s=%s", key, default)
                    self._writebool(key, default)
