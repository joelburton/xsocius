#!/usr/bin/env python

"""Upload built applications to public server and update changes file."""

# IMPORTANT USAGE INFO:
#
# This should be called *after* you've run make.py under both Mac OSX
# and Windows.
#
# You can upload only one name (ie, MooseWords) but the default option
# is to upload all builders. This will take longer to upload, of course.
#
# You must pass in -m for the change message. Users see this when
# they are told of an upgrade.
#
# If you are adding a patch-level upgrade (1.0.0 -> 1.0.1), you can use
# the -b option to specify the base version (1.0.0 in this example).
# Then users on OSX/Windows can use the inplace lightweight update.
# Without this option, they cannot.

import os
import sys
import ftplib
import zipfile
from zipfile import ZipFile
import shutil
import tempfile
import argparse
import datetime
import getpass
from xml.etree import ElementTree

from xsocius.utils import VERSION
from make import ALL

#--- find differences for change file

LIB = '/Contents/Resources/lib/python34.zip'
PLIST = '/Contents/Info.plist'


def walk_to_path(top):
    """Return flat list of all files in tree."""

    lentop = len(top)
    files = []
    for path, dirnames, filenames in os.walk(top):
        files.extend( [ os.path.join(path, f)[lentop:] for f in filenames ])
    return files


def make_change(name, old_ver, version, new=None):
    """Make .zip for help changes and all in new library."""

    # To compare the old version to the new version, we'll always use
    # the old version full app stored in upload -- if, for some reason,
    # this is gone, it must be recreated by running make for that version.

    old = "upload/%s-%s.app" % (name, old_ver)
        
    if not new:
        # Regular make
        #
        # To compare the new version to the base version, we'll use the
        # built app for new version in upload.

        new = "upload/%s-%s.app" % (name, version)
        new_lib = new + LIB
        help_head = "/Contents/Resources/help/"
    else:
        # "Fast" make, where a real app wasn't built.
        #
        # The help files are slightly different places here on disk--what
        # gets made out of this will be the same, though.

        new = new % { 'name': name }
        new_lib = "upload/%s-%s-sp.zip" % (name.lower(), version)
        old = old + "/Contents/Resources/help/"
        help_head = ""

    # If we can't find either of old/new, die

    print("** COMPARING %s to %s" % (old, new))
    if not os.path.exists(old):
        print("** FATAL doesn't exist: %s" % old)
        sys.exit()
    if not os.path.exists(new):
        print("** FATAL doesn't exist: %s" % new)  
        sys.exit()

    ## Check for breaking differences and note any help differences

    old_files = frozenset(walk_to_path(old))
    new_files = frozenset(walk_to_path(new))

    if old_files ^ new_files:
        if new_files - old_files != { '.buildinfo' }:
            print("Only in new %s" % new, new_files - old_files)
            print("old = ", old_files)
            return
        #if old_files - new_files != {'/Contents/Resources/site.pyo'}:
        if old_files - new_files:
            print("Only in old %s" % old, old_files - new_files)
            print("new = ", new_files)
            return

    # Gather help differences
    #
    # Find all differences in apps; only tolerate
    # help differences (note), site-packages.zip (dealt with later),
    # and root/site.pyo (since it changes when app is run, and
    # we don't care about it)
    #
    # All others cause failure

    help_diff = []

    for fname in new_files:
        if ( fname == PLIST
                or fname.endswith('site.pyo')
                or fname.endswith('python34.zip')
                or fname.endswith('.so')
                or fname.endswith('.dylib')
                or fname.endswith('.buildinfo')
                or fname.endswith('/Python')    # dunno why but sometimes Python interp changes?
                    ):
            continue

        ofile = open(old + fname, 'rb')
        nfile = open(new + fname, 'rb')

        if ofile.read() != nfile.read():

            if fname.startswith(help_head):
                help_diff.append(fname[len(help_head):])
                continue

            print("Different CAN'T USE: %s" % fname)
            sys.exit()

        ofile.close()
        nfile.close()

    # Make help differences in zip file like
    #   upload/xsocius-1.1.5-help.zip, containing:
    #      index.html
    #      _static/some-file.css

    print("HELP DIFF: %s" % help_diff)
    help_path = "upload/%s-%s-help.zip" % (name.lower(), version)

    with ZipFile(help_path, 'w', zipfile.ZIP_DEFLATED) as help_zip:
        for fname in help_diff:
            path = new + help_head + fname
            help_zip.write(path, fname)

    #---------- Library Changes

    def _extract(path):
        # Extract xsocius-related .pyo files -- that's all we
        # can patch/care about
        lib = tempfile.mkdtemp()
        with ZipFile(path, 'r') as libzip:
            libzip.extractall(lib, 
                    [f for f in libzip.namelist() 
                        if 'xsocius' in f and f.endswith('.pyo')])
        return lib + "/"

    # Get locations to unzipped xsocius pyo files for old & new

    new = _extract(new_lib)

    new_files = frozenset(walk_to_path(new))

    # Make library differences in zip file like:
    #   upload/xsocius-lib-1.1.5.zip, containing:
    #      xsocius/run.py
    #      xsocius/gui/    ...

    lib_path = "upload/%s-%s-lib.zip" % (name.lower(), version)

    with ZipFile(lib_path, 'w', zipfile.ZIP_DEFLATED) as libzip:
        for fname in new_files:
            libzip.write(new + fname, fname)

    # Return path to helpzip and libzip

    return (help_path, lib_path)
        

#------------------------------------- UPLOADING STUFF

HTML = """
<html>
  <body>
    <img src="%(icon)s" />
    <h1>%(fullname)s</h1>
    <ul>
      <li><b>Latest Mac version: </b><a href="%(dmg)s">%(dmg)s</a><br/>
          <i style="font-size: 80%%; color: #666">
            (at this time, Macs running OSX 10.6+ supported)</i>
      </li>
      <li><b>Latest Windows version: </b><a href="%(exe)s">%(exe)s</a></li>
      <li><b>Latest Python egg (for Linux/other OSes): </b>
          <a href="%(egg)s">%(egg)s</a>
      </li>
    </ul>
  </body>
</html>
"""



def write_version(version, change):
    """Make version file and write to disk."""

    # sample:
    #
    #  <update>
    #    <version>2.0.0</version>
    #    <change>Added something.</change>
    #    <date>2013-04-16</date>
    #  </update>

    xversion = ElementTree.Element('version')
    xversion.text = version

    xchange = ElementTree.Element('change')
    xchange.text = change

    xdate = ElementTree.Element('date')
    xdate.text = datetime.date.today().strftime('%Y-%m-%d')

    xupdate = ElementTree.Element('update')
    xupdate.append(xversion)
    xupdate.append(xchange)
    xupdate.append(xdate)

    xtree = ElementTree.ElementTree(xupdate)
    xtree.write('upload/version.xml')


def dot(x):
    "Feedback."""

    sys.stdout.write(".")
    sys.stdout.flush()     # otherwise buffered until \n


def stor_file(name, ftp, fname, path=None):
    """Upload file to FTP server.
    
    name = name of program (eg, MooseWords)
    ftp = ftp connection
    fname = filename of file to upload
    path = path to file on disk (optional; otherwise upload/{fname}
    """

    if not path:
        path = "upload/" + fname
    print("\n%s" % fname, end=' ')
    with open(path, 'rb') as f:
       ftp.storbinary("STOR public_html/%s/%s" % (name, fname), f,
               blocksize=65536, callback=dot)


def stor_changefiles(name, ftp, changefiles):
    """Store lib/help changes files."""

    for filename in changefiles:
        stor_file(name, ftp, filename[len("upload/"):], filename)


def upload(old_ver, version, change, buildlist=ALL, fast_newpath=None):
    """Upload, possibibly analyzing for changes zips.
    
    old_ver: base version to make change files from
    version: version we're going to upload
    change: change message
    buildlist: list of builders (ie, [MooseWords, Xsocius])
    fast_newpath: this is only set if we're called from make.py (there's
      no way to get this option from the command line here). It's only
      used if we used a "fast" build in make.py, which skips building the
      real app and just makes a dumb package. Since we have to look in
      a slightly different place to find help changes, this tell us where to
      look.
    """


    print()
    print("Version:", version)
    print("Base version:", old_ver)
    print("Builders:", " ".join(buildlist))
    print()

    # Get FTP server, username, password

    default_username = 'joelburton'
    default_server = 'ftp.sonic.net'

    server = input('Server [{}]: '.format(default_server)) or default_server
    username = input('Username [{}]: '.format(default_username)) or default_username
    password = getpass.getpass('Password: ')
    print()

    if not password:
        raise Exception("Password required")

    # Create connection
    print("Making FTP connection.")
    ftp = ftplib.FTP(server, username, password)
    print("FTP connection established.")

    write_version(version, change)
    print("Version file made at upload/version.xml")


    for fullname in buildlist:
        name = fullname.lower()

        print("\n\n" + "-" * 40 + " " + fullname)

        # If we're given an old ver, try to make/upload changes zips
        # and upload to server

        if old_ver:
            changefiles = make_change(name, old_ver, version, fast_newpath)
            if changefiles:
                stor_changefiles(name, ftp, changefiles)
            else:
                print("*** NO CHANGEFILES")
                return

        if not fast_newpath:
            # Only do this stuff in a non-fast upload--since, after all
            # we won't *have* build packages to upload. The webpage
            # will still show the former version but the version.xml
            # file will change--so users will be prompted for a patch-level
            # upgade when they run program.

            dmg = name + "-" + version + ".dmg"
            exe = name + "-" + version + ".exe"
            egg = name + "-" + version + ".egg"
            index = name + "-index.html"

            # Make index.html file and store like upload/moosewords.html
            with open("upload/" + index, 'w') as f:
                f.write(HTML % {'icon': name + '.gif',
                                'fullname': fullname,
                                'egg': egg,
                                'name': name,
                                'dmg': dmg,
                                'exe': exe })
            print("\nMade HTML", end=' ')

            stor_file(name, ftp, dmg)
            stor_file(name, ftp, exe)
            stor_file(name, ftp, egg)
            stor_file(name, ftp, "index.html", "upload/%s-index.html" % name)

        stor_file(name, ftp, "version.xml")

    print("\n\n")
    ftp.quit()


if __name__ == "__main__":

    # Parse cmd line options

    parser = argparse.ArgumentParser(description="Upload packages.")
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument("-m", "--message", metavar="message", 
        required=True,
        help="Changelog message")
    parser.add_argument("-b", "--basever", metavar="version", 
        help="Base version for patch upgrade")
    parser.add_argument("builders", metavar="builder", nargs="*",
        help="Builders to use (defaults to all)", default=ALL)
    args = parser.parse_args()

    upload(args.basever, VERSION, args.message, args.builders)
