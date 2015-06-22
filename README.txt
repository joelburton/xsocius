Notes for Python 3.4:

    virtualenv-3.4 env
    pip install -r requirements.txt

Edit as suggested at:

http://stackoverflow.com/questions/25394320/py2app-modulegraph-missing-scan-code
https://bitbucket.org/ronaldoussoren/py2app/issue/137/py2app-problems-using-enthought-python


To run from the console:

1) DEACTIVATE the virtualenv
2) PYTHONHOME=/Users/joel/from-marcel/marcel-joel/programming/xsocius3/env/ python3.4 -m xsocius.run

To build:

1) ACTIVATE the virtualenv
1) PYTHONPATH=$PYTHONPATH=. python make.py


Posts to http://joelburton.users.sonic.net/pandawords/
