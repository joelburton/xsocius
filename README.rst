XSocius: Desktop Collaborative Crossword Player
===============================================

:Author: Joel Burton <joel@joelburton.com>

.. image:: http://joelburton.users.sonic.net/xsocius/xsocius.gif

Help
----

The application has comprehensive help built-in; you can browse there in the
`help` directory.

Installing
----------

You probably want to get a binary at http://joelburton.users.sonic.net/xsocius/

Alternatively, you can build this, as explained below.

Building
--------

OSX
++++

Requirements: Python 3.4

::

  virtualenv-3.4 env
  pip install -r osx-requirements.txt


Edit installed files as suggested at:

- http://stackoverflow.com/questions/25394320/py2app-modulegraph-missing-scan-code
- https://bitbucket.org/ronaldoussoren/py2app/issue/137/py2app-problems-using-enthought-python

To run from the console::

  PYTHONHOME=$(realpath env) python3.4 -m xsocius.run

To build::

  python make.py


Windows
+++++++

Requirements: Python 3.4

Install virtualenv::

    c:\python34\scripts\pip install virtualenv

Make virtualenv::

    C:\python34\scripts\virtualenv env-win
    env-win\scripts\activate

Install requirements::

  pip install -r win-requirements.txt --trusted-host wxpython.org

To run from console::

  python -m xsocius.run

To build, you need Innoinstaller (open source)::

  python make.py


Linux
+++++

Requirements: Python 3.4, normal building tools

Install requirements::

  sudo apt-get install dpkg-dev build-essential libwebkitgtk-dev libjpeg-dev libtiff-dev libgtk2.0-dev libsdl1.2-dev libgstreamer-plugins-base0.10-dev freeglut3 freeglut3-dev
  pip install -r linux-requirements.txt --trusted-host wxpython.org