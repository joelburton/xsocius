.. _my-web-cookies:

Web Cookies
===========

.. warning:: Advanced Material

   This section suggests how you can automate downloading of puzzles
   from sites that require log in via cookies, such as the New York
   Times premium site. This requires you to edit files on disk in
   very particular formats, and may be challenging for more basic users.

   Alternatively, if this process doesn't work or is confusing, you could 
   always download the paid puzzles using a standard web browser and then 
   open them up as file puzzles.

Some web sites that offer crossword puzzles are subscription sites (most
notably, The New York Times). While the Times offers a free "classic" puzzle
once a week, this is often a decade-old puzzle from their archives. For
access to their daily puzzle, you need a paid subscription.

|NAME| can open web puzzles from many subscription sites, but does
require you to edit a text file to put in the proper cookie information from
the site.

First, using any web browser, go to the subscription site, log in, and
retrieve a puzzle.

Look at the list of cookies stored in your browser. There should be
at least one cookie for the site which is used for log in information
for the site. For some sites, there may be many
cookies stored, many having to do with other features like ads of preferences,
and it may require some experimentation to find the login cookie.

For the New York Times, the log in cookie is called "NYT-S".

Edit the "cookies.txt" file that came with this program. This will be
in different places depending on your operating system:

- *Windows*: in your home directory, in |COOKIES|.

- *Linux*: in your home directory, in |COOKIES|.

- *OSX*: in your home directory, in |COOKIESOSX|.

Edit this file to add a line for your new cookie. A sample line is already in
this file for the New York Times (though the sample cookie data provided is
fictional and won't work).

The format is::

  Set-Cookie3: COOKIENAME="cookie-string"; path="/"; domain=".site.com"; 
    path_spec; domain_dot; expires="expiration-date"; version=0

**This should be entered as one line, without any linebreaks or return
characters** (the example above is on separate lines just to make it more
readable here).  You can copy and paste the cookie string, domain, and
expiration date from your web browser's cookie listing.

If you are trying to enable puzzles for the New York Times, you can simply
replace the sample cookie-string data in the example line with your real cookie
data. For other sites, you can create a new line like the sample one.

