#!/opt/local/bin/python3.3

"""Build Xsocius."""

# IMPORTANT USAGE INFO:
#
# This is the primary building script for Xsocius.
#
# To make a new release:
#
#   ./make.py
#
# Or to limit it to just one builder:
#
#   ./make.py MooseWords
#
# This should be run on both OSX and Windows.
# 
# Once that is done, then you run the FTP script,
# normally as:
#
#   ./ftp.py -m "upload message"
#
# or, for a patch version (1.0.0 -> 1.0.1),
#
#   ./ftp.py -m "msg" -b 1.0.0
#
#
# If you're making a new patch release and you
# don't want to upload the whole new apps (which is
# slow, given their size), you can choose the "fast cafe
# option" (-f) and use this script to just upload
# changes:
#
#   ./make.py -f -m "msg" -b 1.0.0 
#
# ------
#
# Less common/testing options:
#
# You can FTP right from this script by passing in
# the -m option for the upgrade message. This builds
# then FTPs.
#
# If you're building a patch version (1.0.0 -> 1.0.1)
# and you want to upload from here, also supply the
# "base version" (ie, 1.0.0 in the above example).
# This will then upload the changefiles so users can
# do inplace upgrades. Except for testing, there's no
# good reason to not do this when using -m to FTP
# from here.
#
# You can skip doc building with --skip-docs. There's
# no good reason to do this unless you're certain the
# docs haven't changed. It makes things slightly faster.
# You might choose this when building the Windows build
# if you've already run the Mac build--since the docs
# have already been made.
#
# You can skip building with -s. This is only useful if
# you want to use the FTP system from here; it basically
# just patches you through to FTP without building docs
# the app. You *must* have run this once before
# successfully for the version in question. This is kind
# of a dumb option.
#
# You can use a "fast" build with -f. This does not
# build the real app (ie, the Mac clickable app) but
# it does package things up so that you can use -m -b.
# This is only useful if you wanted to release a patch
# version that doesn't have a corresponding full app
# version being uploaded. This might be useful if there's
# an patch-level bugfix where you don't want to or can't
# afford to upload the whole clickable app. 

import sys
import glob
import wx
import re
import os
import os.path
import shutil
import zipfile
import argparse

# XXX: we need to remove dist first for mac, otherwise there are failures!

from xsocius.utils import VERSION as version

NAMERE = re.compile('NAME = ".*?"')
utils = open("xsocius/utils.py", "r").read()
ALL = [ 'PandaWords', 'MooseWords', 'Xsocius'] # , 'LeahWords' ]
STATIC_DIR = os.path.join('xsocius', 'help', '_static')


def decrap_help(name):
    """Remove unused junk from sphinx-made help."""

    for i in glob.glob(os.path.join(STATIC_DIR, '*')):
        if not i in [ os.path.join(STATIC_DIR, 'nature.css'), 
                      os.path.join(STATIC_DIR, 'basic.css'),
                      os.path.join(STATIC_DIR, 'help.css'),
                      os.path.join(STATIC_DIR, '%s.gif' % name.lower()),
                      ]:
            print (i)
            os.remove(i)
    os.remove(os.path.join('xsocius','help','objects.inv'))



def build(name, fast=False, make_docs=True):
    """Build one named version (ie, "PandaWords")"""

    print("\n\n")
    print("-" * 40, name)

    # Update on disk the utils.py module to change the NAME variable
    # to the name of the product we're building.

    _utils = NAMERE.sub('NAME = "%s"' % name, utils)

    with open("xsocius/utils.py", "w", newline='') as f:
        f.write(_utils)


    if fast:

        # Don't build a app; just make an zip file of the
        # pyo modules--useful when uploading just a bugfix version
        # which the inplace upgrader can use.
        #
        # This can only be run on a Mac (or maybe Linux; untested)

        if make_docs:
            os.system("sphinx-build -b singlehtml -d help/_build/doctrees"
                    " help xsocius/help")
            decrap_help(name)
        try:
            shutil.rmtree('build')
        except:
            pass

        # We want a zip file of optimized .pyo files that can be used
        # without the corresponding .py files -- since this is how
        # py2app and py2exe will make things.
        # 
        # In py2.7, this could be done with
        #   python setup.py build_py -O2
        #
        # However, in py3.3, this puts things in __pycache__ -- and that
        # requires that we have the original .py files (as well as not
        # matching how py2app/py2exe do things.
        #
        # So instead we now use compileall with the -b (legacy pyo locations)
        # option. This is called on a copy of the xsocius lib put into
        # build/lib.

        os.system("mkdir build/lib")
        shutil.copytree('xsocius', 'build/lib/xsocius')
        os.system("python -OO -m compileall -b build/lib/xsocius")

        # Now put just the .pyo files in the zipfile (skip over the .py)

        with zipfile.ZipFile("upload/%s-%s-sp.zip" % 
                    (name.lower(), version), 
                "w", 
                zipfile.ZIP_DEFLATED) as zf:
            for i in ( glob.glob("build/lib/xsocius/*.pyo") + 
                       glob.glob("build/lib/xsocius/gui/*.pyo") ):
                zf.write(i, i[len("build/lib/"):])

        # Copy built library files to dist (XXX: why?)
        os.system("mkdir dist/%s" % name)
        os.system("mv build/lib dist/%s/" % name)


    elif wx.Platform == "__WXMSW__":
        
        # Windows: make docs, make exe, turn into installer

        if make_docs:
            os.system("c:\\Python33\Scripts\\sphinx-build.exe -b singlehtml"
                    " -d help\\_build\\doctrees help xsocius\\help")
            decrap_help(name)
        try:
            shutil.rmtree('build')
        except:
            pass

        os.system("c:\\Python33\python -OO setup.py build_exe")
        os.system('"c:\\Program Files (x86)\\Inno Setup 5\\ISCC.exe"'
                ' build\\exe.win32-3.3\\installer.iss')
        shutil.copyfile("build/exe.win32-3.3/Output/setup.exe", 
                "upload/%s-%s.exe" % (name.lower(), version))


    elif wx.Platform == "__WXMAC__":

        # Mac: make docs, py2app, strip unused architecture stuff with ditto,
        #      make dmg and THEN bdist_egg

        if make_docs:
            os.system("sphinx-build -b singlehtml -d help/_build/doctrees"
                    " help xsocius/help")
            decrap_help(name)
        try:
            shutil.rmtree('build')
        except:
            pass

        ARCH = "x86_64"
        os.system("arch -%s python setup.py py2app" % ARCH)

        # Copy the app to the upload directory (use ditto for
        # copying because Python's copyfile will lose the 
        # resource fork.

        os.system("ditto dist/%s-%s/%s.app" % (name, ARCH, name) +
                " upload/%s-%s.app" % (name, version))

        # Copy the dmg to the upload directory.

        shutil.copyfile("dist/%s_%s.dmg" % (name, ARCH), 
                "upload/%s-%s.dmg" % (name.lower(), version))

        # Also make eggs
        os.system("rm dist/*egg")
        os.system("python setup.py bdist_egg")
        os.system("cp dist/*egg upload/%s-%s.egg" % 
                (name.lower(), version))


    elif wx.Platform == "__WXGTK__":

        # Linx: make docs, make bdist_egg

        if make_docs:
            os.system("sphinx-build-3.3 -b singlehtml -d help/_build/doctrees"
                    " help xsocius/help")
            decrap_help(name)
        os.system("rm dist/*egg")
        os.system("python2.7 setup.py bdist_egg")
        os.system("cp dist/*egg upload/%s-%s.egg" % (name.lower(), version))


def upload(message, old_ver, fast, builders):
    """Hand off to FTP upload program."""

    import ftp
    if fast:
        ftp.upload(old_ver, version, message, builders, 
                "dist/%(name)s/lib/xsocius/help/")
    else:
        ftp.upload(old_ver, version, message, builders)



if __name__ == "__main__":

    parser = argparse.ArgumentParser(
            description="Build & optionally upload.")
    parser.add_argument('--version', action='version', version=version)
    parser.add_argument("-f", "--fast", action='store_true',
        help="Fast mode (do not build app; just zip of pyo files)")
    parser.add_argument("-m", "--message", metavar="message", 
        help="Changelog message; providing ftps script results")
    parser.add_argument("-b", "--basever", metavar="version", 
        help="Base version for patch upgrade (only used when FTPing)")
    parser.add_argument("-s", "--skip-build", action="store_true",
        help="Skip building and just upload.")
    parser.add_argument("--skip-docs", action="store_true",
        help="Skip building docs (WARNING: name might be wrong!).")
    parser.add_argument("builders", metavar="builder", nargs="*",
        help="Builders to use (defaults to all)", default=ALL)
    args = parser.parse_args()

    #if args.fast:
    for dist_stuff in glob.glob('dist/*'):
        if os.path.isdir(dist_stuff):
            shutil.rmtree(dist_stuff, ignore_errors=True)
        else:
            os.remove(dist_stuff)

    if not args.skip_build:
        print("\nBuilding for %s" % args.builders)
        for name in args.builders:
            assert name in ALL, "Not builder: %s" % name   
            build(name, args.fast, not args.skip_docs)

    # If we provided a message, then let's upload everything

    if args.message:
        upload(args.message, args.basever, args.fast, args.builders)

