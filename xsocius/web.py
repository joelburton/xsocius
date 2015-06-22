"""Open web-based puzzles."""

import logging
import datetime
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar

import os


class WebPuzzleOpenException(Exception):
    """Couldn't open a puzzle."""


def WebOpener(name, days, url, directory, startat=None, maxtries=3,
              cookiefile=None):
    """Open web puzzle at URL, finding for proper days.
       
       name = Name of puzzle or site (used in GUIs and for file name)
       days = Weekday #s puzzle is available, eg [1,2] for Monday + Tuesday
       url = URL of puzzle (with optional strftime markers)
       directory = Directory to save files
       startat = day to start looking
       maxtries = # of attempts to make
       cookiefile = path of cookiefile (may or may not exist)

       Will start looking at today, unless startat is given, in which case
       this is used instead.

       Will download files up to maxtries # of times.
    """

    # Get cookie file and use, if present
    if cookiefile and os.path.exists(cookiefile):
        logging.info('Using cookie file at %s', cookiefile)
        cookie_jar = http.cookiejar.LWPCookieJar()
        cookie_jar.load(cookiefile)
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar))
        urllib.request.install_opener(opener)
    else:
        logging.info('No cookie file found at %s', cookiefile)

    if startat is None:
        startat = datetime.date.today()

    # Loop back in time from startat, looking on correct weekdays for puzzle.

    tries = 0
    logging.info("Looking for days=(%s) starting at %s from %s",
                 days, startat, url)
    for i in range(0, 1000):

        trydate = startat - datetime.timedelta(i)
        if trydate.isoweekday() in days:
            tryurl = trydate.strftime(url)
            tryfname = "{}/{} {}".format(
                directory, name, trydate.strftime("%m-%d-%y.puz"))

            # Don't re-download puzzles we already have.
            if os.path.exists(tryfname):
                logging.info("WebOpener: found existing %s", tryfname)
                return tryfname

            logging.info("WebOpener: Trying %s at %s to %s",
                         name, tryurl, tryfname)

            try:
                req = urllib.request.Request(tryurl)
                webob = urllib.request.urlopen(req)

                if webob.code == 200:
                    result = webob.read(13)
                    if result.endswith(b'ACROSS&DOWN'):
                        # Found valid puzzle
                        result += webob.read()
                        with open(tryfname, 'wb') as f:
                            f.write(result)
                        return tryfname
                    else:
                        logging.error("WebOpener: %s returned invalid file:" +
                                      " magic=%s", tryurl, result)
                else:
                    logging.error("WebOpener: %s returned web error %s",
                                  tryurl, webob.code)

            except IOError as e:
                logging.error("WebOpener: IOError at %s: %s", tryurl, e)

            tries += 1
            if tries == maxtries:
                raise WebPuzzleOpenException(
                    "Max tries reached at {}.".format(tryurl))

    raise WebPuzzleOpenException(
        "No valid date found. {} {} {}".format(name, days, url))


if __name__ == "__main__":
    print(WebOpener(
        "Onion AV Club",
        [3],  # Wed only
        "http://herbach.dnsalias.com/Tausig/av%y%m%d.puz",
        "/tmp"
    ))
