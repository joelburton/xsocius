#!/opt/local/bin/python3.3

"""Packing script for xsocius."""

# IMPORTANT USAGE INFO:
#
# This is not meant to be used independently, but you could use it.
#
# This is called by make.py to make the apps/eggs; that also does other things, like build the
# help system and put the final files into the right upload/ directory for uploading to an FTP
# server.
#
# This bypasses that if used directly.
#
# Note: this is also used as "setup build_ext" to build cython-based unlocker.

import sys
import glob
import zipfile
from distutils.extension import Extension

import os
import tempfile
import shutil
from setuptools import setup, find_packages
from xsocius.utils import NAME, VERSION, URL, SKIP_UI

FAST = os.environ.get('FAST', False)

# SKIP_UI is only for developer testing of the sharing feature; we don't want to accidentally
# release a version with it turned on.

if SKIP_UI:
    raise Exception("SKIP_UI=True -- this is for developers only")

APP = "xsocius/run.py"
ICNS = "%s.icns" % NAME.lower()

DATA_FILES = [
    ('sounds', glob.glob('xsocius/sounds/*')),
    ('tips', glob.glob('xsocius/tips/*')),
    ('help', glob.glob('xsocius/help/*.*')),
    ('help/_images', glob.glob('xsocius/help/_images/*')),
    ('help/_static', glob.glob('xsocius/help/_static/*')),
    ('icons', glob.glob('xsocius/icons/*')),
]
PACKAGE_FILES = ['sounds/*',
                 'tips/*',
                 'help/*.html',
                 'help/_images/*',
                 'help/_static/*',
                 'icons/*']

settings = dict(
    name=NAME,
    version=VERSION,
    author="Joel Burton",
    author_email="joel@joelburton.com",
    license="GPL",
    url=URL,
    description="Collaborative crossword solving GUI application.",
    long_description=
    "A GUI application for solving crosswords collaboratively.",
    classifiers=[
        'Environment :: MacOS X',
        'Environment :: Win32 (MS Windows)',
        'Environment :: X11 Applications :: GTK',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: ' +
        'GNU General Public License v3 or later (GPLv3+)',
        'Natural Language :: English',
        'Topic :: Games/Entertainment :: Puzzle Games',
    ],
    data_files=DATA_FILES,
    keywords='crossword wxpython gui word puzzle',
    install_requires=['sleekxmpp']
)

# ----------------------------------- OSX APP ----------------------------------

def BuildOSXApp():
    PLIST = dict(CFBundleName=NAME,
                 CFBundleIconFile=ICNS,
                 CFBundleShortVersionString=VERSION,
                 CFBundleGetInfoString="%s %s" % (NAME, VERSION),
                 CFBundleExecutable=NAME,
                 CFBundleIdentifier="com.joelburton.xsocius",
                 CFBundleDevelopmentRegion="English",
                 NSHumanReadableCopyright="Copyright 2013 by Joel Burton",
                 CFBundleDocumentTypes=[dict(
                     CFBundleTypeName='xname',
                     CFBundleOSTypes=['xpuz'],
                     CFBundleTypeExtensions=['puz'],
                     CFBundleMIMETypes=['application/x-crossword'],
                     CFBundleTypeRole='Viewer',
                     LSTypeIsPackage=True
                 )],
                 LSRequiresCarbon=False,
                 )

    settings.update(
        app=[APP, ],
        options={
            'py2app': dict(iconfile=ICNS,
                           argv_emulation=True,
                           arch='x86_64',
                           optimize=2,
                           compressed=True,
                           excludes="xsocius/help",
                           plist=PLIST)},
        setup_requires=['py2app'],
    )

    setup(**settings)

    # At this point, we have an OSX app, but it doesn't quite work.

    # py2app packages up all of the libraries for Python into a zip file. We need to fix it up.
    #
    # There are two problems with it:
    #
    # - It contains junk we don't need in it (Vim swap files, and non-py resources for Xsocius
    #
    # - It contains the dylib for wxPython but in the wrong place
    #
    # Unzip this file to a temp directory, fix up the files, re-zip it up, and replace the
    # original zip with the improved one.

    temp_dir = tempfile.mkdtemp()
    temp_zip = '%s/new.zip' % temp_dir

    lib_path = 'dist/%s.app/Contents/Resources/lib' % NAME
    lib_zip_path = lib_path + '/python34.zip'
    dylib = 'libwx_osx_cocoau-3.0.0.3.0.dylib'
    dylib_temp_dir = '%s/wx/%s' % (temp_dir, dylib)
    dylib_new_dir = '%s/python3.4/lib-dynload/wx/%s' % (lib_path, dylib)

    # Unzip lib zip to temp dir

    with zipfile.ZipFile(lib_zip_path) as old_lib:
        old_lib.extractall(temp_dir)
        files = old_lib.namelist()

    # Move dynlib from unzipped temp dir to place in app

    print("* MOVING %s -> %s" % (dylib_temp_dir, dylib_new_dir))
    shutil.move(dylib_temp_dir, dylib_new_dir)

    # Now, re-zip up, excluding resources & dylibs that shouldn't be the lib zip

    with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as new_lib:
        for path in files:
            if (path.endswith('.swp') or
                        'xsocius/help' in path or
                        'xsocius/tips' in path or
                        'xsocius/sounds' in path or
                        'xsocius/icons' in path or
                    (path.startswith('wx/') and path.endswith('.dylib'))
                ):
                print("* REMOVING %s" % path)
                continue

            new_lib.write(temp_dir + "/" + path, path)

    shutil.copy(temp_zip, lib_zip_path)
    shutil.rmtree(temp_dir)

    # At this point, we have a functional OSX app -- however, it's rather bloated, as it contains
    #  code for alternate architectures (like i386) We'll use "ditto" to strip out the other
    # architectures, making the app about half the size.
    #
    # Then, we use hdiutil to make a .dmg of it, which is used by users to install the app.
    #
    # The original, bloated file is left in place.

    for arch in ['x86_64']:  # , 'ppc','i386']:  XXX until we solve compat
        _ = {'n': NAME, 'a': arch}
        os.mkdir('dist/%(n)s-%(a)s' % _)
        print("DITTO ===========")
        os.system(
            ("ditto --rsrc --arch %(a)s " +
             " dist/%(n)s.app dist/%(n)s-%(a)s/%(n)s.app") % _)
        print("DITTO ===========")
        if not FAST:
            os.system(
                ("hdiutil create ./dist/%(n)s_%(a)s.dmg" +
                 " -srcfolder dist/%(n)s-%(a)s") % _)


# ---------------------------------- LINUX EGG ---------------------------------

def BuildLinux():
    settings.update(
        packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
        zip_safe=False,
        entry_points={'gui_scripts': ['%s = xsocius.run:run' % NAME.lower(), ]},
        data_files=[],
        package_data={'xsocius': PACKAGE_FILES},
    )
    setup(**settings)


# --------------------------------- WINDOWS EXE --------------------------------

def BuildWindows():
    from cx_Freeze import setup, Executable

    settings.update(
        options=
        {"build_exe": {
            'optimize': 2,
            'include_files': [('xsocius\\tips', 'tips'),
                              ('xsocius\\help', 'help'),
                              ('xsocius\\icons', 'icons'),
                              ('xsocius\\sounds', 'sounds')
                              ],
            'include_msvcr': True,
        }
        },
        executables=[
            Executable("xsocius\\run.py",
                       targetName='%s.exe' % NAME,
                       base='Win32GUI')
        ]
    )

    setup(**settings)

    # cx_Freeze can make installers with "bdist_msi", but they are too simple--they don't offer
    # uninstallers, and don't put the program in the Start Menu. So we make it with InnoSetup.
    # Here, we writ a InnoSetup script.
    #
    # (make.py actually runs Inno over this)

    iss = r"""
[Setup]
AppName=%(NAME)s
AppVerName=%(NAME)s %(VERSION)s
AppPublisher=Joel Burton
AppPublisherURL=%(URL)s
DefaultDirName={pf}\%(NAME)s
DefaultGroupName=%(NAME)s

[Files]
Source: "*.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "*.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "%(NAME)s.exe";DestDir: "{app}";Flags:ignoreversion
Source: "library.zip"; DestDir: "{app}"; Flags: ignoreversion
Source: "help\*"; DestDir: "{app}\help"; Flags: ignoreversion
Source: "help\_static\*"; DestDir: "{app}\help\_static"; Flags: ignoreversion
Source: "help\_images\*"; DestDir: "{app}\help\_images"; Flags: ignoreversion
Source: "sounds\*"; DestDir: "{app}\sounds"; Flags: ignoreversion
Source: "icons\*"; DestDir: "{app}\icons"; Flags: ignoreversion
Source: "tips\*"; DestDir: "{app}\tips"; Flags: ignoreversion

[Icons]
Name: "{group}\%(NAME)s"; Filename: "{app}\%(NAME)s.exe"
Name: "{group}\Uninstall %(NAME)s"; Filename: "{uninstallexe}"
""" % {'NAME': NAME, 'URL': URL, 'VERSION': VERSION}

    with open("build/exe.win32-3.3/installer.iss", "w") as f:
        f.write(iss)


# --------------------------------- UNLOCKER -----------------------------------

def BuildUnlocker():
    from Cython.Distutils import build_ext

    print("\n\nIMPORTANT: "
          "This doesn't build all of this program, just the unlocker.\n\n")
    ext_modules = [Extension("unlocker", ["unlocker.pyx"])]

    setup(
        name='Xsocius Unlocker',
        cmdclass={'build_ext': build_ext},
        ext_modules=ext_modules
    )

    shutil.move('build/lib.macosx-10.10-x86_64-3.4/unlocker.so',
                'xsocius/unlocker.so')

# ---------------------------------- RUNNER ------------------------------------

if __name__ == "__main__":
    cmd = sys.argv[1]

    if cmd == "py2app":
        BuildOSXApp()

    elif cmd == "build_exe":
        BuildWindows()

    elif cmd == "bdist_egg":
        BuildLinux()

    elif cmd == "build_py":
        BuildLinux()

    elif cmd == "sdist":
        BuildLinux()

    elif cmd == "build_ext":
        BuildUnlocker()

    else:
        # Keep this here so we can get help on setup.py and perhaps use any other commands (which
        #  aren't needed for the standard build process
        setup()
