"""Support code for ugrades."""

import sys
import logging
import webbrowser
import urllib.request, urllib.parse, urllib.error
import tempfile
import zipfile
import os.path
import shutil
from xml.etree import ElementTree

import wx
import wx.lib.agw.pybusyinfo as PBI

from xsocius.utils import VERSION_URL, VERSION, NAME, URL
from xsocius.gui.utils import makeHeading, makeText
from xsocius.log import DEBUG_MODE


class UpgradeException(Exception):
    """Problem occurred during upgrade."""


class UpgradeDialog(wx.Dialog):
    """Dialog for upgrade notification options."""

    # Title
    # Text
    # Changes
    # Offer
    #
    #      [ok] [cancel]

    def __init__(self, parent, version, change, date):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, 
                title="New Version Available: %s" % version)

        title = makeHeading(self, "A newer version of %s is available!" % NAME)
        explain = makeText(self,
            "You are using version %s" % VERSION + 
            "; the latest is %s." % version + "\n\n" +
            "It was released on %s." % date +
            " Overview of latest version:")
        upgrade = wx.TextCtrl(self, wx.ID_ANY,
                style=wx.TE_MULTILINE|wx.TE_READONLY)
        upgrade.SetValue(change)
        upgrade.SetMinSize((10,120))
        #upgrade.Enable(False)
        offer = makeText(self, "Would you like to download?")

        # Add Ok/Cancel buttons
        btnsizer = wx.StdDialogButtonSizer()
        cancel = wx.Button(self, wx.ID_CANCEL)
        btnsizer.AddButton(cancel)
        self.ok = ok = wx.Button(self, wx.ID_OK, label="Connect")
        btnsizer.AddButton(ok)
        ok.SetDefault()
        btnsizer.Realize()

        outsizer = wx.BoxSizer(wx.VERTICAL)
        outsizer.AddMany( [
                (title, 0, wx.TOP|wx.LEFT|wx.RIGHT, 30),
                (10,10),
                (explain, 0, wx.LEFT|wx.RIGHT, 30),
                (10,10),
                (upgrade, 0, wx.LEFT|wx.RIGHT|wx.EXPAND, 30),
                (20,20),
                (offer, 0, wx.LEFT|wx.RIGHT, 30),
                (15,15),
                (btnsizer, 0, wx.ALIGN_RIGHT|wx.RIGHT, 20),
                (20,20),
                ])
        
        self.SetSizer(outsizer)
        outsizer.Fit(self)
        self.CenterOnScreen()
        upgrade.Bind(wx.EVT_SET_FOCUS, self.moveFocus, upgrade)


    def moveFocus(self, event):
        """Move focus to OK button."""

        self.ok.SetFocus()


def newest_version_info():
    """Download newest version and update message.
    
    Returns tuple of (new-version-#, change-msg, date-as-string)
    """

    try:
        data = urllib.request.urlopen(VERSION_URL).read()
    except Exception as err:
        logging.error("Unable to get latest version info at %s: %s", 
                VERSION_URL, err)
        return (None, None, None)

    # version.xml contains the new version #, a change msg, and the date:
    #
    #  <update>
    #    <version>2.0.0</version>
    #    <change>Added something.</change>
    #    <date>2013-04-16</date>
    #  </update>

    root = ElementTree.fromstring(data)
    version = root.find('version').text
    change = root.find('change').text
    date = root.find('date').text

    logging.info("Found upgrade: %s: %s", version, change)
    return version, change, date


def prompt_update_version(window, version, change, date):
    """Given a version and update message, show box."""

    if version is None or version <= VERSION:
        # Can't get version info or is right version
        return

    if DEBUG_MODE:
        # We're running in debug mode -- ie, from a console and therefore
        # a developer. So don't pester us about upgrades.
        return

    dlg = UpgradeDialog(window, version, change, date)
    result = dlg.ShowModal()
    dlg.Destroy()

    if result == wx.ID_CANCEL:
        # Declined upgrade
        return

    currver = VERSION
    newver = version
    busy = PBI.PyBusyInfo("Getting upgrade...")
    wx.Yield()
    changes = get_changes_files(currver, newver)

    if not changes:
        # Can't autoupgrade; open browser
        webbrowser.open(URL, new=2)
    else:
        # Try auto-upgrade
        tmpdir, changefile, helpfile = changes
        try:
            apply_changes(tmpdir, changefile, helpfile, currver, newver)
        except UpgradeException as e:
            del busy
            wx.MessageBox(
                "In-place upgrade failed: %s.\n\n" % e +
                "You should do a manual upgrade."
                )
            webbrowser.open(URL, new=2)
        else:
            del busy
            wx.MessageBox(
                "Upgrade successful.\n\n"
                "Restart is required. Press OK to quit.")
            wx.Exit()


def get_changes_files(currver, newver):
    """Fetch the changes files if possible.
    
    These are two files: a zipfile of the Xsocius libraries and a zipfile
    of the help files.

    Return (temp directory path, lib zip filename, help zip filename)
    """

    # Only works with OSX and Windows (for now)
    if wx.Platform not in ['__WXMAC__', '__WXMSW__']:
        return

    # Only allow patch upgrades (ie 1.0.3 -> 1.0.4, not -> 1.1.0)
    cmaj, cmin, cpatch = currver.split('.')
    nmaj, nmin, npatch = newver.split('.')

    if nmaj != cmaj or nmin != cmin:
        logging.debug("Not patch level upgrade; manual required.")
        return
    
    name = NAME.lower()
    tmpdir = tempfile.mkdtemp()

    retfiles = []

    # Download lib zipfile and help zipfile

    for kind in ['lib', 'help']:
        url = "{url}/{name}-{ver}-{kind}.zip".format(
                url=URL, name=name, ver=newver, kind=kind)
        path = os.path.join(tmpdir, kind) + '.zip'
        logging.info("Trying %s changes file at %s", kind, url)
        try:
            filename, headers = urllib.request.urlretrieve(url, path)
        except urllib.error.HTTPError:
            # If we can't donwload the changes file, then we'll punt--
            # the code that calls us should suggest the user does a full
            # manual upgrade. This can happen if we upload a patch
            # version that should have an upgrade-lib-fileset, but if we
            # fail to upload them. Der.
            logging.info("Couldn't find %s changes file at %s", kind, url)
            return
        if "zip" in headers['content-type']:
            logging.info("Got %s changes file at %s to %s", kind, url, path)
            retfiles.append(filename)
        else:
            logging.info("Failed: %s", headers['content-type'])
            return

    return tmpdir, retfiles[0], retfiles[1]

        
def apply_changes(tmpdir, libchanges, helpchanges, currver, newver):
    """Given library and help changes, apply."""

    # Get list of change files and extract them to temp directory
    change_zip = zipfile.ZipFile(libchanges, "r")
    changed_files = change_zip.namelist()
    change_zip.extractall(tmpdir)
    change_zip.close()
    logging.debug("Applying changes in temp directory " + tmpdir)

    # find our site-packages.zip
    for path in sys.path:
        if ( path.endswith("/python34.zip") or
             path.endswith(r"\library.zip") ):
            break
    else:
        raise UpgradeException("Cannot find library in our sys.path")

    logging.debug("Upgrading library at " + path)

    # Add changed files to our site-packages.zip
    #
    # This appends them to the end of the existing zip file so if 
    # foo.pyo changes, there will technically be 2 versions of it in
    # the zip file. However, Python only uses the last one for imports,
    # so it will work out. These files are small enough that it
    # won't matter.

    try:
        site_packages = zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED)
        for changed_file in changed_files:

            # XXX: for Windows, we create .pyc files, not .pyo files
            # but the base has .pyc files, so let's rename them .pyo.
            # ugh. hackity hack hack.
             
            if wx.Platform == '__WXMSW__':
                new_name = changed_file.replace('.pyo', '.pyc')
            else:
                new_name = changed_file

            logging.debug("Upgrading %s: %s", path, new_name)

            site_packages.write(
                    os.path.join(tmpdir, changed_file), new_name)
        site_packages.close()

    except Exception as e:
        raise UpgradeException("%s" % e)

    logging.debug("Finished upgrading libraries")

    # Find location of library file
    # For Windows, this is location of help.
    # For OSX, it's up 1

    path = os.path.split(path)[0]
    if wx.Platform == '__WXMAC__':
        path = path + '/../help'
    elif wx.Platform == '__WXMSW__':
        path = path + '/help'
    else:
        raise Exception("Unsupported OS")

    path = os.path.abspath(path)

    # Get help files and extract to path
    change_zip = zipfile.ZipFile(helpchanges, "r")
    changed_files = change_zip.namelist()
    logging.info("Unzipping help files to %s: %s", path, changed_files)
    change_zip.extractall(path)
    change_zip.close()

    # Clean up temp directory
    shutil.rmtree(tmpdir)

    # if we're on a Mac, update our plist file so that the system shows
    # the new version # in the finder for the application.

    if wx.Platform == '__WXMAC__':
        plistpath = os.path.abspath(path + '/../../Info.plist')
        logging.debug("Updating plist file at %s", plistpath)
        with open(plistpath, 'r') as f:
            plist = f.read()
        plist = plist.replace(currver, newver)
        with open(plistpath, 'w') as f:
            f.write(plist)
        logging.debug("Plist updated.")

    logging.debug("Upgrade done.")

