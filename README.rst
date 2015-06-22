XSocius: Desktop Collaborative Crossword Player
===============================================

:Author: Joel Burton <joel@joelburton.com>

.. raw:: html

  <img src="http://joelburton.users.sonic.net/xsocius/xsocius.gif">

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
  pip install -r requirements.txt


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

Make virtualenv

    C:\python34\scripts\virtualenv env-win
    env-win\scripts\activate

Install requirements::

  pip install -r wrequirements.txt --trusted-host wxpython.org

To run from console::

  python -m xsocius.run

To build, you need Innoinstaller (open source)::

  python make.py