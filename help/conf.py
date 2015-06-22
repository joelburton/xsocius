import sys, os
from xsocius.utils import NAME, VERSION

templates_path = ['_templates']
master_doc = 'index'
project = NAME
copyright = u'Copyright 2013 by Joel Burton'
version = release = ""
exclude_patterns = ['_build']
html_theme = 'nature'
html_static_path = ['_static']
html_show_sphinx = False
html_show_copyright = False
htmlhelp_basename = "xsocius"
html_logo = "../xsocius/icons/%s.gif" % NAME.lower()
html_sidebars = { '*': ['localtoc.html']}
html_copy_source = False
html_compact_lists = False
html_style = "help.css"


rst_epilog = """
.. |NAME| replace:: %s
.. |COOKIES| replace:: `.%s`
.. |COOKIESOSX| replace:: `Library/Application Support/%s`
.. |rarr|   unicode:: U+02192 .. RIGHTWARDS ARROW
""" % (NAME, NAME, NAME)
