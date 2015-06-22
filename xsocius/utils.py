"""Useful utilities used by Xsocius modules."""

# Configurable stuff

NAME = "Xsocius"
VERSION = "3.1.0"
URL = "http://joelburton.users.sonic.net/%s" % NAME.lower()
VERSION_URL = URL + "/version.xml"

# Set this to true for testing the sharing system--it allows
# easier connections for using the same computer as both
# client and server. It is only referred to by the share.py
# module. Note that the build system will fail-by-design when
# this is set to True; we don't want to release versions with
# this feature turned on.
SKIP_UI = False

#---------------------------------------------------------------------

import os.path

def suggestSafeFilename(directory, fname):
    """Suggest a safe 'copy of' filename.

       Given a directory and a filename, this will find a similar name
       that does not exist. It first adds "Copy of" in front of the name
       and, if that exists, increases a count at the end.
    """
    
    while True:
        attempt = os.path.join(directory, fname)

        if not os.path.exists(attempt):
            # success!
            break

        if not fname.startswith('Copy Of '):
            fname = "Copy Of " + fname
            continue

        prefix, ext = os.path.splitext(fname)
        if " " not in fname:
            fname = "%s 2%s" % (prefix, ext)
            continue

        prenum, num = prefix.rsplit(" ", 1)
        if len(num) > 2:
            # Doesn't look like one of our numbers, so add ours
            fname = "%s 2%s" % (prefix, ext)
            continue

        if not num.isdigit():
            # Not a num, so add ours
            fname = "%s 2%s" % (prefix, ext)

        # Increment the number
        num = int(num) + 1
        fname = "%s %s%s" % (prenum, num, ext)

    return fname


if __name__ == "__main__":
    for i in range(5):
        path = suggestSafeFilename('/tmp', 'pear bean.puz')
        with open("/tmp/" + path, 'w') as f:
            f.write("hello")
