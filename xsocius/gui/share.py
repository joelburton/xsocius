"""Sharing panel and supporting code."""

import os
import re
import base64
import logging
import bz2
import webbrowser

import wx
import wx.adv
import wx.lib.agw.pybusyinfo as PBI

# For some reason, Windows isn't able to load ElementTree under py2exe.
# Loading this once solves the problem.
import xml.etree.ElementTree

import sleekxmpp
from sleekxmpp.exceptions import IqTimeout

# These are dynamically loaded by the system, and so py2app for Mac
# doesn't know to package them up. There must be a better way to trick
# the system into knowing to include them in packages.

import sleekxmpp.features.feature_starttls
import sleekxmpp.features.feature_mechanisms
import sleekxmpp.features.feature_bind
import sleekxmpp.features.feature_session
import sleekxmpp.features.feature_rosterver
import sleekxmpp.features.feature_preapproval
import sleekxmpp.plugins.xep_0047
import sleekxmpp.plugins.xep_0030

from xsocius.utils import suggestSafeFilename, SKIP_UI, NAME, VERSION
from xsocius.gui.utils import makeHeading, makeHint, makeText
from xsocius.gui.utils import get_sound, font_scale


JOIN_MSG = "Join me for a game of " + NAME + "! I'm at " 

PROTOCOL_VERSION = 1


# def user_and_nick_from_jid(jid):
#     """For joel@server.com/1xfoo, return (joel, joel@server.com)"""
# 
#     user = jid.split('/', 1)[0]
#     nick = jid.split('@', 1)[0]
# 
#     return user, nick

# How long should notification highlights of a friend move last? (in ms):
HIGHLIGHT_LENGTH = 700

# Process of sharing:
#
# One computer ("sharer") opens a puzzle normally then chooses to share it.
# They are prompted for username/password for XMPP server. An XMPP connection
# is made and stored as .xmpp. Authentication proceeeds. Once authenticated,
# they can send an invite to a friend; this is essentially just a text message
# that gives the JID of the sharer. Sending the invite is optional and whether
# it is sent or not does not affect the process.
#
# The other computer ("joiner") may or may not have a puzzle open, but, if so,
# it won't be the shared puzzle, anyway. When they know they want to join a 
# puzzle (perhaps they received an invite IM in their normal IM software), they
# choose to join from the menu. This promps for XMPP connection info (same
# dialog as sharer). They store the .xmpp connection and start authentication.
# Once authenticated, they are prompted for the JID of the sharer. This JID is
# stored as .friend and .friendnick.  (If they already have the request-JID
# dialog open when the specially formatted invite text message is sent,
# this is noticed and things proceed as if they manually entered the JID).
# Either case, they then send a "HELLO" command to the 
# sharer to let them know they're ready.
#
# When the sharer receives the HELLO, they now know the ID of their "friend";
# this is stored as .friend and .friendnick. They then send a FILE command, 
# letting the joiner know to prepare to receive the initial puzzle file. 
# This is followed by sending the file in a data packet to the joiner.
#
# When the joiner receives the FILE command, they know that the connection
# attempt was successful (and hide the "waiting connection" dialog). They get
# the file and open it in a new window. Since the window they had before isn't
# really related to sharing, .xmpp, .friend, and .friendnick are removed from 
# it and set on the new window.
#
# At this point, the two machines are now in the same state and act the same--
# the can send messsages, SET moves, CLEAR, CHECK, REVEAL, and HIGHLIGHT to
# each other. A machine can send DISCONNECT to the other machine to inform it
# of its intent to disconnect.

# 2.0 future goal: the sharer should now be able to share with more than one person;
# friend -> [friends], friendnick -> [friendnick], and we should iterate over 
# the list of people to send things like messages to. In addition, when we
# are the sharer and receive a message, we should iterate over people that 
# aren't the sender to rebroadcast it.

#--------------------- Dialogs Used in Process

def addLogOnDialogOptions(self, config):
    """Add connection options to logon dialog."""

    # Since we ask the same server/user/password questions both during
    # the sharing process and in the preferences panel for sharing,
    # this is factored out for use in both places.

    self.server = wx.TextCtrl(self, wx.ID_ANY, config.server)
    self.username = wx.TextCtrl(self, wx.ID_ANY, config.username)
    self.password = wx.TextCtrl(self, wx.ID_ANY, config.password, 
            style=wx.TE_PASSWORD)
    lserver = wx.StaticText(self, wx.ID_ANY, "Server")
    lusername = wx.StaticText(self, wx.ID_ANY, "Username")
    lpassword = wx.StaticText(self, wx.ID_ANY, "Password")
    hserver = makeHint(self, 'For Google Talk, this is "talk.google.com".')
    husername = makeHint(self, 
            'For Google Talk, this is usually "you@gmail.com".')

    sizer = wx.FlexGridSizer(5, 2, 5, 5)
    sizer.AddMany([ 
            (lserver), 
            (self.server, 0, wx.EXPAND), 
            (0, 0),
            (hserver),
            (lusername), 
            (self.username, 0, wx.EXPAND), 
            (0, 0),
            (husername),
            (lpassword), 
            (self.password, 0, wx.EXPAND) 
            ])
    sizer.AddGrowableCol(1, 1)
    return sizer


class LogOnDialog(wx.Dialog):
    """Dialog for log on options."""

    server = None
    username = None
    password = None

    # Server:   ________
    # Username: ________
    # Password: ********
    #
    #      [ok] [cancel]

    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title="Enter Connection Information")

        sizer = addLogOnDialogOptions(self, wx.GetApp().config)

        outsizer = wx.BoxSizer(wx.VERTICAL)
        outsizer.Add(sizer, 0, wx.ALL, 15)

        # Add Ok/Cancel buttons
        btn_sizer = wx.StdDialogButtonSizer()
        cancel = wx.Button(self, wx.ID_CANCEL)
        btn_sizer.AddButton(cancel)
        self.ok = ok = wx.Button(self, wx.ID_OK, label="Connect")
        btn_sizer.AddButton(ok)
        ok.SetDefault()
        outsizer.Add(btn_sizer, flag=wx.ALIGN_RIGHT)
        btn_sizer.Realize()

        self.SetSizer(outsizer)
        outsizer.Fit(self)
        self.CenterOnScreen()

        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdate)

    def OnUpdate(self, event):
        """Allow OK to be used only when all the fields are filled."""

        if event.GetId() == self.ok.GetId():
            event.Enable( bool(self.server.GetValue())  and
                          bool(self.username.GetValue()) and
                          bool(self.password.GetValue()))
        else:
            event.Skip()


class XMPPWaitDialog(wx.Dialog):
    """Dialog box that shows we're waiting to get puzzle from sharer.
    
       Ends in one of several ways:
       - manually canceled (user got bored waiting for reply);
         ultimately fires off disconnection
       - system calls EndModal passing ID_CANCEL (got an error while trying
         to join a puzzle); ultimately fires off disconnection
       - system calls EndModal passing ID_OK (got notice it would get
         the puzzle file).
    """

    # Connecting Message
    #
    #           [cancel]

    def __init__(self, parent, title, msg):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title)

        sizer = wx.BoxSizer(wx.VERTICAL)
        text = wx.StaticText(self, wx.ID_ANY, msg)
        btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        sizer.Add(text, 0, wx.ALL, 20)
        sizer.Add(btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 20)
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, btn)
        self.CenterOnScreen()

    def OnCancel(self, event):
        """Cancel button hit."""

        self.EndModal(wx.ID_CANCEL)
        self.Parent.XMPPDisconnect()


class JoinFriendDialog(wx.Dialog):
    """Dialog box that prompts to join a user.

       Ends in one of several ways:
       - manually canceled; caused disconnection
       - filled in by user; tries to join
       - system calls EndModal with JID of friend; this is done if we actually
         get the invite
    """

    # Prompt
    # 
    # _____________
    #
    #   [ok][cancel]

    def __init__(self, parent, err_msg, default):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, "Connect to Friend")

        text = makeHeading(self, "Waiting for Automatic Invitation.")
        text2 = makeHint(self,
                         "This prompt will disappear once automatic invitation is received.")
        if err_msg:
            err_msg_text = makeText(self, err_msg_text)
            err_msg_text.SetForegroundColour("#663333")
            err_msg_object = (err_msg_text, 0, wx.TOP | wx.LEFT | wx.RIGHT, 10)
        else:
            err_msg_object = (0, 0)

        hint = makeHint(self,
                        "If you can't use automatic invites, enter invitation code.\n"
                        "You probably received this in your IM client.\n"
                        "Valid codes look like 'joel@server.com/1xwords1234ABCD'.")
        self.join = wx.TextCtrl(self, wx.ID_ANY)
        if default:
            self.join.SetValue(default)

        # Add Ok/Cancel buttons

        btn_sizer = wx.StdDialogButtonSizer()

        cancel = wx.Button(self, wx.ID_CANCEL)
        btn_sizer.AddButton(cancel)

        self.ok = ok = wx.Button(self, wx.ID_OK, label="Connect")
        btn_sizer.AddButton(ok)
        ok.SetDefault()

        btn_sizer.Realize()

        outer_sizer = wx.BoxSizer(wx.VERTICAL)
        outer_sizer.AddMany([
            (text, 0, wx.TOP | wx.RIGHT | wx.LEFT, 20),
            (7, 7),
            (text2, 0, wx.LEFT | wx.RIGHT, 20),
            (10, 10),
            (hint, 0, wx.LEFT | wx.RIGHT, 20),
            (10, 10),
            err_msg_object,
            (10, 10),
            (self.join, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20),
            (btn_sizer, 0,
             wx.ALIGN_RIGHT | wx.RIGHT | wx.LEFT | wx.TOP | wx.BOTTOM, 20)
        ])
        self.SetSizer(outer_sizer)
        outer_sizer.Fit(self)



#--------------------- Sharing Panel left of gameboard


class MsgList(wx.TextCtrl):
    """Sharing message list."""

    def __init__(self, parent):
        wx.TextCtrl.__init__(self,
                             parent,
                             wx.ID_ANY,
                             style=wx.TE_MULTILINE | wx.TE_RICH2 | wx.TE_READONLY | wx.TE_AUTO_URL)

        # Determine colors & sizes
        _fontsize = font_scale(12)

        self.IM_NORMAL_FONT = wx.Font(_fontsize,
                                      wx.FONTFAMILY_DEFAULT,
                                      wx.FONTSTYLE_NORMAL,
                                      wx.FONTWEIGHT_NORMAL)
        self.IM_NAME_FONT = wx.Font(_fontsize,
                                    wx.FONTFAMILY_DEFAULT,
                                    wx.FONTSTYLE_NORMAL,
                                    wx.FONTWEIGHT_BOLD)
        self.IM_COMMENT_FONT = wx.Font(_fontsize,
                                       wx.FONTFAMILY_DEFAULT,
                                       wx.FONTSTYLE_SLANT,
                                       wx.FONTWEIGHT_NORMAL)
        self.IM_NORMAL_COLOR = "#000000"
        self.IM_COMMENT_COLOR = "#888888"
        self.IM_NAME_COLOR = "#111166"  # blue-grey

        self.SetDefaultStyle(wx.TextAttr(self.IM_NORMAL_COLOR, font=self.IM_NORMAL_FONT))

        self.Bind(wx.EVT_TEXT_URL, self.OnURLClick)

    def OnURLClick(self, event):
        """Open links in browser."""

        mouse = event.GetMouseEvent()
        if mouse.GetEventType() == wx.EVT_LEFT_DOWN.typeId:
            url = self.GetValue()[event.GetURLStart():event.GetURLEnd()]
            webbrowser.open(url, new=2)

    def addMessage(self, friendnick, msg):
        """Adds a message to this box; the sender is in the NAME font."""

        self.SetInsertionPointEnd()
        before = self.GetInsertionPoint()
        self.AppendText("%s: %s\n" % (friendnick, msg))
        self.SetStyle(before, 
                      before + len(friendnick) + 1, 
                      wx.TextAttr(self.IM_NAME_COLOR, font=self.IM_NAME_FONT))

    def addComment(self, comment):
        """Adds a comment to the box; this is in COMMENT font."""

        self.SetInsertionPointEnd()
        before = self.GetInsertionPoint()
        self.AppendText(comment + "\n")
        self.SetStyle(before, 
                      before + len(comment), 
                      wx.TextAttr(self.IM_COMMENT_COLOR,  font=self.IM_COMMENT_FONT))

    def flash(self):
        """Flash IM box to show message received."""

        self.SetBackgroundColour("#FFBBBB")
        wx.CallLater(HIGHLIGHT_LENGTH/2, self.unflash)

    def unflash(self):
        """Remove flash of box."""

        self.SetBackgroundColour("White")


class MsgEntry(wx.TextCtrl):
    """Sharing message entry."""

    def __init__(self, parent):
        # On OSX, there appears to be a bug where multiline textcontrols do not process ENTER;
        # this is annoying for the chat box, so let's make it single-line and able to process
        # ENTER (auto-URL also does not work on OSX)
        if wx.Platform == '__WXMAC__':
            styles = wx.TE_PROCESS_ENTER | wx.TE_AUTO_URL
        else:
            styles = wx.TE_PROCESS_ENTER | wx.TE_MULTILINE | wx.TE_AUTO_URL

        wx.TextCtrl.__init__(self, parent, wx.ID_ANY, size=(100, 50), style=styles)
        self.puzzle_window = self.GetTopLevelParent()
        self.Bind(wx.EVT_TEXT_ENTER, self.OnEnter)
        self.Bind(wx.EVT_TEXT_URL, self.OnURLClick)
        self.Bind(wx.EVT_SET_FOCUS, self.IHaveFocus)

    def IHaveFocus(self, event):
        """We have focus; unfocus other things."""

        logging.debug("MsgEntry has focus")
        pw = self.GetTopLevelParent()
        pw.board.unfocusBoard()
        pw.across_clues.highlight(pw.across_clues.curr)
        pw.down_clues.highlight(pw.down_clues.curr)

    def OnURLClick(self, event):
        """Open URL in browser."""

        # Only works on GTK and MSW

        mouse = event.GetMouseEvent()
        if mouse.GetEventType() == wx.EVT_LEFT_DOWN.typeId:
            url = self.GetValue()[event.GetURLStart():event.GetURLEnd()]
            webbrowser.open(url)

    def OnEnter(self, event):
        """Send message and append to list."""
            
        msg = self.GetValue().strip()
        self.Clear()

        if msg:
            self.puzzle_window.XMPPSendMsg(msg)

        # If user has preference set, focus returns to the board after
        # every message -- but in any case, if they press return on a
        # blank message, focus returns to the board.

        if not msg or wx.GetApp().config.autoend_im:
            self.puzzle_window.board.SetFocus()


class SharingPanel(wx.Panel):
    """Panel for sharing list and entry."""

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY)

        self.puzzle_window = self.GetTopLevelParent()
        self.sizer = wx.BoxSizer(wx.VERTICAL)

        self.puzzle_window.msg_list = MsgList(self)
        label = makeHeading(self, "Send Message:")

        self.puzzle_window.msg_entry = MsgEntry(self)
        hint = makeHint(self, "Shortcut: '/' to focus here.")

        self.sizer.Add(self.puzzle_window.msg_list, 10, wx.EXPAND)
        self.sizer.Add(label, 0, wx.TOP, 10)
        self.sizer.Add(self.puzzle_window.msg_entry, 0,  wx.EXPAND | wx.BOTTOM | wx.TOP, 4)

        if wx.Platform == '__WXGTK__':
            logging.debug("Adding Send button for GTK")
            self.send = wx.Button(self, wx.ID_ANY, 'Send')
            self.sizer.Add(self.send, 0, wx.RIGHT | wx.ALIGN_RIGHT, 5)
            self.Bind(wx.EVT_BUTTON, self.puzzle_window.msg_entry.OnEnter, self.send)

        self.sizer.Add(hint)
        self.SetSizer(self.sizer)
        if wx.Platform == "__WXMAC__":
            # This seems a little self-evident, but it needed to workaround
            # display bug in OSX Mountain Lion
            self.SetBackgroundColour(parent.GetBackgroundColour())


#--------------------- GUI classes


class Friend(object):
    """Class to represent a friend we're connecting or connected with."""

    jid = None
    nick = None
    version = None

    JID_RE = re.compile("([^@]*)@[^/]*/(\d)xwords.*")

    def __init__(self, jid):
        """Return username, version from JID."""

        logging.info("Making Friend from %s", jid)
        self.jid = jid

        match_obj = self.JID_RE.match(jid)
        if match_obj:
            self.nick, self.version = match_obj.groups()

    def __repr__(self):
        return "<Friend jid='{0.jid}' nick='{0.nick}' version='{0.version}'>".format(self)


class ShareWindowMixinBase:
    """Sharing for both joiner and sharer.
    
    In order to provide the functionality needed for sharing, the GUI Puzzle
    object subclasses sharing-specific mixins. This mixin is a base of those
    behaviors that are same whether this is the sharer or joiner.
    """

    # Underlying XMPP connection object. This is used both as the interface
    # to the XMPP system (ie, things are called on the object), but also as
    # a marker for us to know that there is a connection -- if this is None,
    # there's no connection.
    xmpp = None

    # Friends we're connected to will get connected to this as a dict.
    # For joiners, this will only ever be one person; for sharers, it can
    # be more than one.
    #
    #   { 'joel@server.com/resource': Friend(..), ... }
    # 

    # Pointer to cancelable dialog showing joining is awaiting file send
    # from sharer.
    joining_wait_dialog = None

    # Pointer to busybox showing connecting to server
    connecting_busy_box = None

    # Joining dialog open; waiting for user to enter JID of friend
    joining_dialog_open = None

    # Are we in the process of disconnecting?
    xmpp_disconnecting = False

    # Are there highlights on the board?
    has_highlights = False


    def __init__(self):
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateSharing)

        config = wx.GetApp().config
        self.im_sound = config.im_sound
        self.im_flash = config.im_flash

        self.friends = {}


    #--- Menu options

    def OnUpdateSharing(self, event):
        """Only show menu options if applicable."""

        if self.dummy:
            # Dummy window has none of these menu options anyway
            event.Skip()
            return

        eid = event.GetId()

        if eid == self.ID_DISCONNECT:
            event.Enable(self.xmpp is not None)

        elif eid == self.ID_HIGHLIGHT:
            event.Enable(self.xmpp is not None)

        elif eid == self.ID_HIGHLIGHT_CLR:
            event.Enable(getattr(self, 'has_highlight', False))

        elif eid == self.ID_REINVITE:
            event.Enable(self.xmpp is not None and self.xmpp.is_sharer)

        else:
            event.Skip()


    def OnHighlight(self, event):
        """Highlight word for friend."""

        cells = [ cell.xy for cell in self.puzzle.curr_word() ]
        self.xmpp.send_highlight(cells)
        self.XMPPHighlight(cells)
        self.has_highlight = True


    def OnHighlightClr(self, event):
        """Clear highlight."""

        for row in self.puzzle.grid:
            for cell in row:
                cell.highlight = False
        self.board.DrawNow()

        self.has_highlight = False


    def OnDisconnect(self, event):
        """Disconnect."""

        self.XMPPDisconnect()


    #--- Initiating Connection


    def XMPPConnectDialog(self):
        """Show connection options dialog and return results."""

        config = wx.GetApp().config
        if SKIP_UI or config.skip_conn_dlg:
            return (config.server, config.username, config.password)
        else:
            dlg = LogOnDialog(self)
            result = dlg.ShowModal()
            dlg.Destroy()

            if result == wx.ID_OK:
                server = dlg.server.GetValue()
                username = dlg.username.GetValue()
                password = dlg.password.GetValue()
                return (server, username, password)

        return (None, None, None)
    

    def XMPPConnect(self, server, username, password, is_sharer):
        """Connect to server."""

        logging.info("xmpp connect")
        self.connecting_busy_box = XMPPWaitDialog(self, "Connecting",
                "Attempting to establish connection to %s." % server)
        self.connecting_busy_box.Show()

        if self.xmpp is not None:
            # Must be re-joining with /rejoin command -- so let's
            # keep the existing friend info.

            friends = self.friends
            # XXX where do we get friend info from?
            logging.info(
                    "Reconnecting from same window: friends=", self.friends)

        else:
            friends = {}

        invisible = wx.GetApp().config.invisible
        self.xmpp = Connection(username+"/%sxwords" % PROTOCOL_VERSION, 
                               password, 
                               self, 
                               is_sharer, 
                               invisible)

        self.friends = friends
        self.xmpp_sharer = is_sharer

        if is_sharer:
            # Attach connection to logical puzzle object (if we're not a sharer,
            # there may not be a puzzle yet--this could be the dummy window)
            self.puzzle.xmpp = self.xmpp

        # All things being equal, we'd rather not reattempt connections, but
        # it appears sleekxmpp first tries an IPv6 lookup for google talk
        # and, if we don't allow retry, we'll never get the IPv4 connection.

        logging.error("ca.certs = %s", self.xmpp.ca_certs)
        self.xmpp.reconnect_max_attempts = 2
        self.xmpp.response_timeout = 2
        self.xmpp.wait_timeout = 2

        if self.xmpp.connect((server, 5222), reattempt=True):
            wx.Yield()
            logging.info("xmpp process starting")
            self.xmpp.process(block=False)
        else:
            logging.error("xmpp connect failed")
            self.close_busy_box()
            dlg = wx.MessageDialog(None, 
                    "Error connecting.", 
                    "Error", 
                    style=wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            self.xmpp = None


    def XMPPShowSharePanel(self):
        """Show sharing panel on puzzle window."""
             
        if not self.share_panel.IsShown():
            self.share_panel.Show()
            w, h = self.GetSize()
            if w < 800:
                self.SetSize((w+180, h))
            elif w < 900:
                self.SetSize((w+100, h))
    
            self.splitter.InsertWindow(0, self.share_panel, 180)
            self.OnSize(None)


    #--- Used during shared game

    def close_busy_box(self):
        """Close connecting wait box."""

        if self.connecting_busy_box:
            if self.connecting_busy_box.IsModal():
                self.connecting_busy_box.EndModal(wx.ID_OK)
            self.connecting_busy_box.Destroy()
            self.connecting_busy_box = None


    def XMPPDisconnect(self, msg="Goodbye", noecho=False,
            skip_disentangling=False):
        """End connection.
        
        msg: message to send to our friend
        noecho: we're doing this because friend told us they're
           disconnecting; no need to tell them
        skip_disentangling: when rejoining, we just want to
           cut the actual xmpp connection--but not close the
           sharing panel, etc.
        """

        logging.info("XMPPDisconnect start")

        # We get an exception if we later try to actually do an
        # xmpp disconnect while it's already happening, so let's
        # use a flag to prevent calling this while we're already
        # disconnecting.

        if self.xmpp_disconnecting: 
            logging.error("XMPP disconnect already in progress")
            return

        self.xmpp_disconnecting = True

        # Notify friends, but we don't care if it fails--we might be
        # disconnecting because of a network problem and can't reach them
        if not noecho:
            self.xmpp.send_disconnect(msg)

        # If we're the sharer and the game didn't start, let's first get rid
        # of the "waiting" dialog
        if self.joining_wait_dialog:
            self.joining_wait_dialog.EndModal(wx.ID_CANCEL)
            # Exit, because this will call us again from the top
            self.xmpp_disconnecting = False
            return

        busy = PBI.PyBusyInfo("Disconnecting; please wait...")
        try:
            wx.Yield() # Fixes bug that doesn't show busy box on GTK.
        except Exception:
            pass

        if self.xmpp:
            # XXX under what circumstances could this be called where
            # there is no self.xmpp?
            try:
                # It's tempting to take the wait=True out of the next line
                # to make disconnections faster--but this isn't waiting for
                # the disconnection to finish, it's waiting to send queued
                # messages before the disconnection happens. There doesn't seem
                # to be way to do async disconnects.
                self.xmpp.disconnect(wait=True)
            except Exception as e:
                logging.error("Couldn't disconnect, %s", e)
        
        if not skip_disentangling:
            # Do this if we're not rejoining right now
            self.xmpp = None
            if not self.dummy:
                self.puzzle.xmpp = None

            if not self.dummy and self.share_panel.IsShown():
                self.msg_list.Clear()
                self.splitter.DetachWindow(self.share_panel)
                self.share_panel.Hide()

        logging.info("XMPPDisconnect finish")
        self.xmpp_disconnecting = False


    def XMPPReceiveMsg(self, msg, mfrom=None):
        """Receive IM message in UI.

           Add to the IM window.
        """

        # mfrom is an xmpp JID object; turn to string like "joel@.../res"
        mfrom = str(mfrom)

        logging.info("XMPPReceive from %s", mfrom)

        if JOIN_MSG in msg and self.joining_dialog_open:
            # We're the joiner and we currently are awaiting the invite
            # and this is it. Fill the information out in the dialog and
            # press OK -- just like the human would if this were manually done.

            logging.info("Got invite from %s", mfrom)
            self.joining_dialog_open.join.SetValue(mfrom)
            self.joining_dialog_open.EndModal(wx.ID_OK)
            return

        msg_from = Friend(mfrom)

        if msg_from.jid not in self.friends:
            # This message is from someone we're not playing with
            logging.error(
                    "Message before friend was set: %s from %s", msg, mfrom)
            return

        if msg.startswith("/me "):
            msg = "%s %s" % (msg_from.nick, msg[4:])
            self.XMPPShowComment(msg)

        elif msg.startswith("/popup "):
            msg = msg[7:]
            wx.MessageBox(msg)
            return

        elif msg.startswith("/version"):
            self.xmpp.send_message("/me is using %s %s" % (NAME, VERSION))
            return

        else:
            # An ordinary message; show it
            self.msg_list.addMessage(msg_from.nick, msg)

        if self.im_sound:
            sound = wx.adv.Sound(get_sound("im.wav"))
            sound.Play()

        if self.im_flash:
            self.msg_list.flash()


    def XMPPSendMsg(self, msg):
        """Send IM message via UI.
        
           Send message then update IM window.
        """

        if msg.startswith("/disconnect"):
            bye = msg[len("/disconnect "):]
            self.XMPPDisconnect(msg=bye)
            self.XMPPShowComment("You disconnect.")
            return

        if msg.startswith("/rejoin"):
            # Rejoin a broken connection. Only the joiner should do this
            # and it's not really documented. Opens a new window on the same
            # puzzle. Useful if the connection seems borked.
            self.XMPPDisconnect("[no message]",
                    noecho=True, skip_disentangling=True)
            self.OnJoin(None)

        elif msg.startswith("/me "):
            # Show us the /me message like friends will see it
            status = "%s %s" % (self.xmpp.boundjid.user, msg[4:])
            self.XMPPShowComment(status)

        else:
            # Show us our message in the message list
            self.msg_list.addMessage("you", msg)

        # Actually send the message

        if self.friends:
            self.xmpp.send_message(msg)
        else:
            self.msg_list.addComment("You are not yet connected to anyone.")


    def XMPPShowComment(self, comment):
        """Show comment in IM window."""

        self.msg_list.addComment(comment)


    def XMPPClearHighlight(self, cells):
        """Remove the highights on the cells.

           This is called by wx.CallAfter; when a cell is highlighted, this is
           timed to be called later, so the highlight is temporary.
        """

        flag = False
        for cell in cells:
            if cell.highlight:
                flag = True
                cell.highlight = False
        if flag:
            self.board.DrawNow()


    def XMPPSetCell(self, x, y, val, rebus):
        """Set a cell answer, highlight cell, and sched the de-highlighting."""

        cell = self.puzzle.grid[x][y]
        self.puzzle.setResponse(cell, val, rebus, noecho=True)
        cell.highlight = True
        self.board.DrawNow()
        wx.CallLater(HIGHLIGHT_LENGTH, self.XMPPClearHighlight, [cell])

        # This might have just completed the puzzle or finished a clue, 
        # so let's make sure those kinds of things are checked for.
        #
        # XXX except that setResponse already calls add_undo which calls
        # this.
        #
        # self.puzzle.on_any_change()


    def XMPPClearCells(self, cells):
        """Clear cells, highlight cleared cells, and sched de-highlighting.
        
        We're passed a list of (x,y) tuples.
        """

        if cells == ["*", "*"]:
            self.restartPuzzle()
            return

        cells_ = [ self.puzzle.grid[x][y] for x, y in cells ]
        for cell in cells_:
            self.puzzle.setResponse(cell, None, None, noecho=True)
            cell.highlight = True
        self.board.DrawNow()
        wx.CallLater(HIGHLIGHT_LENGTH, self.XMPPClearHighlight, cells_)
        

    def XMPPCheckCells(self, cells):
        """Check cells, highlight them, and sched the de-highlighting.
        
        This is called when our friend did a check and we're asked to make
        the same check.

        We're passed a list of (x,y) cells or [*,*] for check-board.
        """

        flag = False
        highlights = []
        grid = self.puzzle.grid

        if cells == ["*","*"]:
            # Check the entire board 
            if self.puzzle.check_puzzle(noecho=True):
                # Something was found as an error, so highlight entire board
                # (technically, given that we're called, something must have
                # been found, since this request isn't sent out unless an
                # error was found. But being cautious.)
                flag = True
                highlights = [ cell for row in grid for cell in row ]
                for c in highlights:
                    c.highlight = True
        else:
            # Check just the given cells. 
            for x, y in cells:
                cell = grid[x][y]
                if self.puzzle._check_letter(cell):
                    flag = True
                    highlights.append(cell)
                    cell.highlight = True
                    
        if flag:
            # If any cells were changed, re-draw and time the un-highlighting
            self.board.DrawNow()
            wx.CallLater(HIGHLIGHT_LENGTH, self.XMPPClearHighlight, highlights)
        

    def XMPPRevealCells(self, cells):
        """Reveal cells, highlight them, and sched the de-highlighting."""

        any_changed = False
        highlights = []
        grid = self.puzzle.grid

        if cells == ["*","*"]:
            # Reveal entire board
            if self.puzzle.reveal_puzzle(noecho=True):
                any_changed = True
                highlights = [ cell for row in grid for cell in row ]
                for c in highlights:
                    c.highlight = True
        else:
            # Reveal just the given cells
            for x, y in cells:
                cell = grid[x][y]
                if self.puzzle._reveal_letter(cell):
                    any_changed = True
                    highlights.append(cell)
                    cell.highlight = True

        if any_changed:
            # If any cells were changed, re-draw and time the unhighlighting
            self.board.DrawNow()
            wx.CallLater(HIGHLIGHT_LENGTH, self.XMPPClearHighlight, highlights)

            # This might have solved the puzzle or changed which clues are
            # completed; check for this kind of stuff.
            self.puzzle.on_any_change()


    def XMPPHighlight(self, cells):
        """Highlight the cells.

           This is called in response to a %HIGHLIGHT command--it means
           to highlight the cells and leave them lit up (no de-highlighting
           is scheduled).
        """

        for x, y in cells:
            self.puzzle.grid[x][y].highlight = True

        self.board.DrawNow()

        self.has_highlight = True


    def XMPPNotifyLost(self, mfrom):
        """Notify that partner dropped."""

        del self.friends[mfrom]
        
        if not self.friends:
            # We have no friends left
            dlg = wx.MessageDialog(self,
                    "The connection to %s seems to"
                    " have been broken.\n\n"
                    "This may be because they've disconnected, or might be a"
                    " problem on your end.\n\n"
                    "If this is a problem, check your network connection"
                    " and try again.\n" % mfrom, 
                    "Connection Dropped", 
                    wx.OK|wx.ICON_ERROR)
        else:
            # We have friends left
            others = "\n".join(
                    [ "  - %s" % f for f in self.friends ] )
            dlg = wx.MessageDialog(self,
                    "The connection to %s seems to"
                    " have been broken.\n\n"
                    "This may be because they've disconnected, or might be a"
                    " problem on your end.\n\n"
                    "If this is a problem, check your network connection"
                    " and try again.\n\n"
                    "You are still connected to:\n%s\n" % (mfrom, others),
                    "Connection Dropped", 
                    wx.OK|wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()

        if not self.friends:
            logging.info("Lost last friend, disconnect.")
            self.XMPPDisconnect()



class ShareWindowMixin(ShareWindowMixinBase):
    """Mixin for puzzles for sharing functionality."""

    def __init__(self):
        ShareWindowMixinBase.__init__(self)
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateShare)


    def OnUpdateShare(self, event):
        """Only show share option if we're not sharing now."""

        eid = event.GetId()

        if eid == self.ID_SHARE:
            event.Enable(self.xmpp is None)
        else:
            event.Skip()


    def OnShare(self, event):
        """Share puzzle.

           Prompt for connection informarion, then initiate connection.
        """

        server, username, password = self.XMPPConnectDialog()

        if server is not None:
            self.XMPPConnect(server, username, password, is_sharer=True)


    def OnResendInvitation(self, event):
        """Menu item to re-send invite."""

        # We want to send another invite. Despite the name, we're not
        # neccessarily resending to the same person--in fact, we prompt
        # for the list of buddies and you could pick someone else.

        self.XMPPFriendInvite(self.recent_buddies)


    def XMPPFriendInvite(self, buddies):
        """Offer to send invitation out.

           Performed only by the sharer. This will send a single textual
           IM to the potential friend. This is not the full JID, so it will
           appear in clients like GTalk.

           It is not required that this be sent out or received--the
           sharer could communicate the JID via offline means. This is 
           just a convenience.
        """

        if self.xmpp_disconnecting: 
            return

        # So that we can send another invite, let's cache the list of
        # buddies.

        self.recent_buddies = buddies

        # The "connecting" busybox may still be open; close it

        self.close_busy_box()

        if SKIP_UI:
            # For developer testing purposes, we just send an invite to
            # ourself
            config = wx.GetApp().config
            self.xmpp.send_invite(config.username)
            self.XMPPShowSharePanel()
            return

        # We may have IDs & names for buddies, or just IDs. Sort the list
        # by name-or-ID.
        buddies = sorted(buddies, 
                key=lambda x: (x[0].lower() if x[0] else x[1].lower(), 
                               x[1].lower()))

        labels = [ "%s (%s)" % (name, jid) if name else jid 
                        for name, jid in buddies ] 

        dlg = wx.MultiChoiceDialog( None, 
                'You can choose one or more users to send an invitation to:', 
                'Send Invites?',
                labels,
                wx.CHOICEDLG_STYLE)
        result = dlg.ShowModal()
        dlg.Destroy()

        # Whether or not they send an invite, they're still going into
        # sharing mode (they might want to send an invite manually)
        # so show the sharing panel.

        self.XMPPShowSharePanel()

        selected = dlg.GetSelections()

        if result == wx.ID_OK and selected:
            for sel in selected:
                friend = buddies[sel][1]
                logging.info("Sending invite to %s", friend)
                self.xmpp.send_invite(friend)
                # self.xmpp.invited_waiting = True
        else:
            self.XMPPShowComment(
                    "You can manually invite friend with invitation code: %s\n---" %
                    self.xmpp.boundjid)


    def XMPPNotifyBadInvite(self):
        """Notify that invite probably failed."""

        dlg = wx.MessageDialog(self,
                ("It appears the invitation was not sent.\n\n"
                 "You can give the connection code directly to your friend."
                 "\n\nYour connection code is:\n%s.\n\n"
                 "To disconnect, click Cancel.\n") % self.xmpp.boundjid,  
                "Invitation Failed",
                wx.OK|wx.CANCEL|wx.ICON_ERROR)
        response = dlg.ShowModal()
        dlg.Destroy()
        if response == wx.ID_CANCEL:
            self.XMPPDisconnect()




class JoinWindowMixin(ShareWindowMixinBase):
    """Mixin for puzzles for joining functionality.

       Join can be used even when a puzzle is not open; if used when
       a puzzle is opened, another window would be opened for joined
       puzzle, anyway (just like File -> Open)
    """

    def __init__(self):
        ShareWindowMixinBase.__init__(self)
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdateJoin)


    def OnUpdateJoin(self, event):
        """Only show Join if we're not joined/sharing."""

        if event.GetId() == self.ID_JOIN:
            logging.debug("Updating join, self.xmpp=%s", self.xmpp)
            event.Enable(self.xmpp is None)
        else:
            event.Skip()


    def OnJoin(self, event):
        """Get connection information."""

        server, username, password = self.XMPPConnectDialog()

        if server is not None:
            self.XMPPConnect(server, username, password, is_sharer=False)


    def XMPPJoinFriend(self):
        """Request friend connection ID.

           Performed only by joining computer, the user must enter the
           JID for the sharer. This is stored as the friend and a
           %HELLO greeting is sent, which will initiate the puzzle
           transfer and play.
        """

        if self.xmpp_disconnecting: 
            return

        self.close_busy_box()

        if SKIP_UI:
            # For developer testing purposes, we can bypass this dialog
            # and just read the invite code off disk.
            f = open("/tmp/invite")
            friend_jid = f.read()
            friend = Friend(friend_jid)
            self.friends[friend_jid] = friend
            self.xmpp.send_hello()
            return 


        errmsg = None
        
        # JID entered into dialog
        friendtry = ""

        while True:

            # Show the join-your-friend dialog; we will be passing
            # in an error message and the JID-entered before if this
            # loops a second or more time.

            # This dialog can be closed by the user clicking OK or
            # cancel but it can also be closed programmatically, if
            # we hear an invite code while it's open. Therefore,
            # we attached the dialog to ourself as joining_dialog_open
            # so that if that invite comes across, we can fill it out
            # and press OK in code.

            dlg = self.joining_dialog_open = JoinFriendDialog(
                    self, errmsg, friendtry)

            result = dlg.ShowModal()
            self.joining_dialog_open = None
            dlg.Destroy()

            if result == wx.ID_OK:
                # If they did a bad copy-paste from the invite sentence,
                # they may have left a trailing person at end.
                friendtry = dlg.join.GetValue().strip(".")

                friend = Friend(friendtry)
                if not friend.nick:
                    errmsg = "Not a valid invitation ID."

                else:
                    self.friends[friendtry] = friend

                    # Actually try to connect with them; this is
                    # asyncronous, so it returns before we know if it
                    # worked.

                    self.xmpp.send_hello()

                    self.joining_wait_dialog = XMPPWaitDialog(self, "Joining",
                            "Waiting to complete connection with friend.")

                    # Show a dialog saying that we're joining and set a flag
                    # during the waiting-for-join process. When the
                    # join has completed, code elsewhere will close the modal
                    # dialog and this will continue.

                    self.xmpp.tentative = True
                    ret = self.joining_wait_dialog.ShowModal()
                    logging.info("post joining_wait_dialog")

                    # The user might cancel the dialog directly, but typically,
                    # we wait here until the system uses EndModal (ID_OK) to
                    # show that the file is being sent & the game is starting.

                    self.joining_wait_dialog.Destroy()
                    self.joining_wait_dialog = None
                    self.xmpp.tentative = None
                    if ret == wx.ID_CANCEL:
                        errmsg = "Joining that user failed. Try again."
                        del self.friends[friendtry]
                        # and let's try again
                    else:
                        break
                        # worked!
            else:
                self.XMPPDisconnect()
                break


    def XMPPJoiningWaitWorked(self):
        """We are receiving the file; presss OK in the joining status box."""

        if self.joining_wait_dialog:
            self.joining_wait_dialog.EndModal(wx.ID_OK)
            logging.info("Joining Wait worked.")


    def XMPPJoined(self, orig_filename, puzzle_data):
        """Handle joining.
        
        We've joined a puzzle and via xmpp have received the data for the
        puzzle. Save it to disk in our crosswords directory and then open it
        up.

        Whatever window is already open (dummy or a real puzzle), it's
        not the puzzle we just received over the wire, so let's move the
        .xmpp connection from the current window and attach it to the
        new window with the puzzle we're now sharing.
        """

        # If this is a rejoin, we didn't ask for friend ID and so
        # we might still have the connecting-busy-box up.
        self.close_busy_box()

        directory = wx.GetApp().config.getCrosswordsDir()
        filename = suggestSafeFilename(directory, orig_filename)
        path = os.path.join(directory, filename)
        with open(path, "wb") as f:
            f.write(puzzle_data)

        logging.info("Joining new crossword")
        new_window = wx.GetApp().open_puzzle(path)
        new_window.puzzle.xmpp = new_window.xmpp = self.xmpp
        new_window.friends = self.friends
        self.friends = {}
        self.xmpp = None
        if not self.dummy:
            self.puzzle.xmpp = None
        new_window.xmpp.wxc = new_window

        new_window.XMPPShowSharePanel()

        # Since we're a joiner, we'll only have one friend
        friend_jid = list(new_window.friends.keys())[0]

        new_window.XMPPShowComment("Joined %s.\n---" % friend_jid)

        if not self.dummy and self.share_panel.IsShown():
            # We're currently on a shared crossword puzzle--so we
            # must be rejoining. Let's close the sharing panel on this
            # puzzle
            logging.info("removing xmpp from current puzzle")
            self.msg_list.Clear()
            self.splitter.DetachWindow(self.share_panel)
            self.share_panel.Hide()


#--------------------- Underlying XMPP Connection Class


class Connection(sleekxmpp.ClientXMPP):
    """XMPP connection object.

       This handles all of the actual wire communication. The wx app
       can call methods directly on this. When this wants to notify the
       wx app of things, it will use wx.CallAfter to request a wx call.
    """

    # For sharer: Connection is made but game is not yet underway
    tentative = False

    # Sent invite, but waiting XXX
    #invited_waiting = False



    def __init__(self, jid, password, wxc, is_sharer, invisible) : 
        """Create connection.

        This is the logical connection the xmpp process. Just because
        we're creating this doesn't mean we're actually logged onto
        a server--that's the connect() call on this object.

        jid: our user id
        password: password
        wxc: the wx connection (ie, the puzzle window)
        is_sharer: True if we're the sharer
        invisible: connect without revealing to world we're online
        """

        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        # Add plugin specific to file transfer; used only to send
        # the initial puzzle.

        self.register_plugin('xep_0047')
        self['xep_0047'].auto_accept = True

        # Add pointer to the WX object. We can use this to refer
        # to the GUI from within the XMPP threads. This object is the
        # puzzle window.
        #
        # We SHOULD NOT use this for anything except binding
        # wx.CallAfter() to callable and for simple property
        # lookup.

        self.wxc = wxc

        self.add_event_handler("session_start", self.session_start) 
        self.add_event_handler("roster_update", self.roster_update, 
                disposable=True) 
        self.add_event_handler("message", self.message) 
        self.add_event_handler('ibb_stream_data', self.handle_data)
        self.add_event_handler('ssl_invalid_cert', self.ssl_invalid_cert)
        self.add_event_handler('failed_auth', self.failed_auth)

        self.auto_reconnect = False

        self.filename = None

        # Puzzle file may arrive in several pieces; they're aggregated
        # in this
        self.data_chunks = []

        self.is_sharer = is_sharer
        #self.friends = {}
        self.invisible = invisible

    #--- XMPP Handlers


    def ssl_invalid_cert(self, event):
        """Invalid SSL certification."""

        # Lots of people have a Jabber JID that isn't related to the hostname
        # of the jabber server (ie, my JID is "joel@joelburton.com" and the
        # hostname is "talk.google.com" (Google Apps account).

        # So let's ignore this.

        return


    def failed_auth(self, event):
        """Username/password problem.

           Show error and disconnect.
        """

        wx.CallAfter(self.wxc.close_busy_box)
        dlg = wx.MessageDialog(None, 
                "There was an error authenticating with the server.\n\n" +
                "If you'd like to retry, please check username and password.", 
                "Authentication Error", style=wx.OK|wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()
        wx.CallAfter(self.wxc.XMPPDisconnect)


    def session_start(self, event): 
        """Server connection has been successfully made.
            
           The sharer will request a roster (which, when returned, will
           ultimately be shown to use for an invite).

           The joiner will be prompted for the sharer JID.
        """

        if not self.invisible:
            # If we're not using the inivisible preference, let's
            # announce our status to the world.
            status = "xwords-share" if self.is_sharer else "xwords-join"
            self.sendPresence(pstatus=status, pshow="dnd", ppriority="50")

        if self.is_sharer:
            try:
                # Ask for the roster. Despite the parameter, this doesn't
                # entirely block--this method will return before we
                # receive the roster; the roster is captured by the handler
                # roster_update, below.
                self.getRoster(block=True)

            except IqTimeout:
                # Wasn't successful; let wx know so we get a connection
                # lost message
                wx.CallAfter(self.wxc.XMPPNotifyLost, mfrom)

        elif self.wxc.friends:
            # We already have a friend, so we're rejoining. No need to
            # prompt for invite code; let's just say hello again.
            self.send_hello()

        else:
            # We don't have a friend, so let's ask for our invite code.
            wx.CallAfter(self.wxc.XMPPJoinFriend)


    def roster_update(self, roster):
        """Get roster of buddies and supply to GUI to send an invite.
        
        The sharer get this when xmpp sends the list of buddies; fix it up
        and call wx to put up the send-invite-to-friend dialog.
        """

        subs = roster.findall("*/{jabber:iq:roster}item[@subscription='both']")
        buddies = [ (b.get('name'), b.get('jid')) for b in subs ]
        wx.CallAfter(self.wxc.XMPPFriendInvite, buddies)

        
    def send_invite(self, friend):
        """Send invitation to play."""

        # Note that unlike other things, the friend here is the jabber ID
        # (joel@joelburton.com) not the full JID (joel@joelburton.com/resource)
        # so it can appear in normal gchat clients.

        msg = "%s%s." % (JOIN_MSG, self.boundjid)
        self.sendMessage(friend, msg)

        # Note in our window that we sent invite
        wx.CallAfter(self.wxc.XMPPShowComment, 
                "Sent to %s: %s\n---" % (friend, msg))

        if SKIP_UI:
            # For developer debug mode, we skip the need to actually enter
            # invite codes and just write our JID to disk--the joiner
            # will read this file and just connect to it.
            f = open("/tmp/invite", "w")
            f.write(str(self.boundjid))
            f.close()

    #--- Handlers

    def message(self, message): 
        """XMPP message received handler.

           Messages are used for almost all gameplay commands as well
           as IMs between players.

           Commands all start with %COMMANDNAME. IMs cannot start
           with a %.
        """

        body = message['body']

        try:
            mfrom = message['from']
        except:
            logging.critical("bad msg? %s", message)
            mfrom = ""

        if message['type'] == "error":
            logging.error("XMPP Error message: %s", message)
            error = str(message['error'])

            if self.tentative:
                # We're the joiner, and haven't yet confirmed
                # so this is a fatal error
                wx.CallAfter(self.wxc.XMPPDisconnect)
            
            elif "service-unavailable" in error:

                if not self.wxc.friends:
                    # XXX: re-evaluate for multi-friend
                    # We're the sharer, and we sent an invite that failed
                    logging.error("Invite seems to have failed")
                    if not SKIP_UI:
                        # If this is during testing, though, just skip --
                        # since we can't actually send an invite to ourselves
                        # and that's what developer testing mode tries to do
                        wx.CallAfter(self.wxc.XMPPNotifyBadInvite)

                elif self.wxc.joining_dialog_open is not None:
                    # We're the joiner, and we entered a bad invite code.
                    # Nothing required to do here, it already knows
                    # the code didn't work
                    pass

                else:
                    logging.error("Service unavailable received")
                    wx.CallAfter(self.wxc.XMPPNotifyLost, mfrom)

            # Uncertain what we should do if the error isn't 
            # service-unavailable but we punt and do nothing but log it

            return


        # If we're the sharer, it's our responsibility to rebroadcast messages
        # to friends who didn't send us this. We don't rebroadcast
        # connection stuff, like %HELLO or %DISCONNECT, but do want to
        # send along normal instant messages and other commands
        rebroadcast = True

        if body.startswith('%'):

            # All commands are like "%COMMAND args" -- split these parts
            cmd, data = body.split(" ", 1)

            if   cmd == "%HELLO":
                self.recv_hello(data)
                rebroadcast = False
            elif cmd == "%DISCONNECT":
                self.recv_disconnect(data, mfrom)
                rebroadcast = False
            elif cmd == "%FILE":
                rebroadcast = False
                self.recv_file(data)

            elif cmd == "%SET":        self.recv_set(data)
            elif cmd == "%CLEAR":      self.recv_clear(data)
            elif cmd == "%CHECK":      self.recv_check(data)
            elif cmd == "%REVEAL":     self.recv_reveal(data)
            elif cmd == "%HIGHLIGHT":  self.recv_highlight(data)

            else:
                logging.error("XMPP unknown command: %s from %s", body, mfrom)

        else:
            # Treat as instant message
            wx.CallAfter(self.wxc.XMPPReceiveMsg, body, mfrom)

        if self.is_sharer and rebroadcast:
            others = [ f for f in self.wxc.friends if f != mfrom ]
            for other in others:
                logging.info("rebroadcasting to %s: %s", other, body)
                self.send_message(body, only_to=other)


    def send_message(self, message, only_to=None):
        """Send message.
        
        Normally, we send everything to everyone. However, in some
        cases, we want to only send a message to one person.
        """

        if not self.wxc.friends:
            logging.info("Attempt to send message without friend: %s", message)
            return

        if only_to:
            logging.info("send_msg only to %s: %s", only_to, message)
            self.sendMessage(only_to, message)
            
        else:
            for friend in self.wxc.friends:
                logging.info("send_msg to %s: %s", friend, message)
                self.sendMessage(friend, message)

        # It seems as if google throttles us if we go to fast
        # and messages are sent back to us (erk)
        #
        # perhaps this won't be a problem with normal people
        # or maybe it will -- and we'll need to have a pipeline in the
        # object that wx writes to and then self-throttles sending it out
        # for now, just slow down a bit.
        #
        # UPDATE: this doesn't seem to be a problem at normal game speeds.

        #time.sleep(0.15)


    def handle_data(self, event):
        """Handle receipt of puzzle by joiner.

           Normal commands and IMS are sent as messages; this is used
           just for sending the initial puzzle.

           Puzzles are sent as base64'd bzipped .puz files; because there is
           a size limit to data packets, it may be split into multiple
           messages--the last message has \n\n%END at the end.
        """

        data_chunk = event['data']

        if self.filename:
            if data_chunk.endswith(b"\n\n%END"):

                # This it the last chunk (of 1 one of more)
                # Join all chunks together and remove
                # end marker.

                self.data_chunks.append(data_chunk)
                allchunks = b"".join(self.data_chunks)
                data = allchunks.rstrip(b"\n\n%END") 

                # Decode and decompress puzzle data
                cdata = base64.decodestring(data)
                puzzle = bz2.decompress(cdata)

                # Tell wx to make us a puzzle window with the new puzzle
                wx.CallAfter(self.wxc.XMPPJoined, self.filename, puzzle)
                self.filename = None

            else:
                # Not the last chunk, save it.
                self.data_chunks.append(data_chunk)

        else:
            logging.critical(
                    "critical error: data rec'd outside file transfer")


    #---- Utilities

    def _cells_to_string(self, cells):
        """Turn a list of cells into a x,y;x,y;x,y string."""

        return ";".join(["%s,%s" % (x, y) for x, y in cells])


    def _string_to_cells(self, data):
        """Turn x,y;x,y;x,y string into list of cells."""

        if data == "*,*": 
            return [ "*","*" ]

        cells = []
        for cell in data.split(";"):
            x, y = cell.split(",")
            cells.append((int(x), int(y)))

        return cells


    #---- Command senders & parsers

    def send_hello(self):
        """Say hello to join sharer.

           Issued only by joiner to initiate contact. The sharer
           should respond with a %FILE command and proceed
           puzzle transfer.
        """

        self.send_message("%HELLO " + str(self.boundjid))

        if not self.invisible:
            # Now that we're greeting our sharer, we no longer
            # need to keep a presence on xmpp -- so we can
            # switch back to being unavailable. Note that if we
            # were also logged into xmpp via another client [like
            # gchat], we'll still be available, as that's a different
            # jabber resource.
            #
            # Don't do this if we are in invisible mode, since we
            # never changed our presence to available anyway.

            self.sendPresence(ptype="unavailable", ppriority="0")


    def recv_hello(self, data):
        """Receive hello and begin puzzle transfer.

           Performed only by sharer.
        """

        friend_jid = data

        # Note that we've started sending the file but haven't yet
        # been fully joined by the joiner. XXX doesn't seem to be used
        #self.invited_waiting = False

        if not self.invisible:
            # Now that we're greeting our joiner, we no longer
            # need to keep a presence on xmpp -- so we can
            # switch back to being unavailable. Note that if we
            # were also logged into xmpp via another client [like
            # gchat], we'll still be available, as that's a different
            # jabber resource.
            #
            # Don't do this if we are in invisible mode, since we
            # never changed our presence to available anyway.
            self.sendPresence(ptype="unavailable", ppriority="0")

        # The sharer learns the JID of the joiner from %HELLO data
        friend = Friend(friend_jid)
        self.wxc.friends[friend_jid] = friend

        # Send the current puzzle.

        # Push changes we've made to puzzle down the file level
        # so we're sending the up-to-date puzzle
        self.wxc.puzzle.update_pfile()

        self.send_file(friend_jid,
                       self.wxc.puzzle.filename, 
                       self.wxc.puzzle.pfile.to_string())

        wx.CallAfter(self.wxc.XMPPShowComment, "Joined by %s\n---" % friend_jid)


    def send_file(self, friend, filename, data):
        """Send file.

           Performed only by sharer to send puzzle.

           Initially, %FILE <puzzlepath>.
           This is followed by a data send of the puzzle,
           bzip2'ed, base64'd, and ending with \n\n%END.
        """

        #self.send_message("%FILE " + filename)   # XXX to just one friend!
        self.sendMessage(friend, "%FILE " + filename)

        # This should use a packetsize of 4K; almost all puzzles
        # should fit under that once bzip2'd; in the chance it does not,
        # it will be spit and recv_file should handle multiple
        # packages.

        cdata = bz2.compress(data)
        data = base64.encodestring(cdata) + b"\n\n%END"
        ibb = self['xep_0047'].open_stream(friend)
        ibb.sendall(data)
        ibb.close()


    def recv_file(self, data):
        """Receive %FILE and prepare for file reception.

           Performed only by slave for receiving puzzle.
           Command is %FILE <filename>.

           Note that this isn't the receipt of the actual file--
           the file command just tells us the puzzle name and
           to prepare to receive the file as a separate 
           xep_0047 data transfer.
        """

        # Note what the filename is and prepare to receive it;
        # the actual file data is handled in handle_data, above.

        logging.info("%FILE recv")

        # We now know that the joiner recognizes us, so we can
        # get rid of the waiting-to-join dialog box.
        wx.CallAfter(self.wxc.XMPPJoiningWaitWorked)

        self.filename = data
        self.data_chunks = []


    def send_set(self, x, y, val, rebus=None):
        """Set a letter on board.

           %SET x,y V [rebus]
        """

        if rebus:
            self.send_message("%%SET %s,%s %s %s" % (x, y, val, rebus))
        else:
            self.send_message("%%SET %s,%s %s" % (x, y, val))


    def recv_set(self, data):
        """Receive %SET and set letter on board."""

        pt, val = data.split(" ", 1)
        x, y = pt.split(",")
        x, y = int(x), int(y)
        if len(val) > 1:
            val, rebus = val.split(" ", 1)
        else:
            rebus = None

        wx.CallAfter(self.wxc.XMPPSetCell, x, y, val, rebus)


    def send_clear(self, cells):
        """Clear cell(s) or entire board.

           %CLEAR x,y[;x,y;x,y...]  or %CLEAR * for board
        """

        self.send_message("%%CLEAR %s" % self._cells_to_string(cells))


    def recv_clear(self, data):
        """Receive %CLEAR and clear cell(s)."""

        cells = self._string_to_cells(data)
        wx.CallAfter(self.wxc.XMPPClearCells, cells)


    def send_check(self, cells):
        """Check cell(s) or entire board.

           %CHECK x,y[;x,y;x,y...]  or %CHECK * for board
        """

        self.send_message("%%CHECK %s" % self._cells_to_string(cells))


    def recv_check(self, data):
        """Receive %CHECK and check cell(s)."""

        cells = self._string_to_cells(data)
        wx.CallAfter(self.wxc.XMPPCheckCells, cells)


    def send_reveal(self, cells):
        """Reveal cell(s) or entire board.

           %REVEAL x,y[;x,y;x,y...]  or %REVEAL * for board
        """

        self.send_message("%%REVEAL %s" % self._cells_to_string(cells))


    def recv_reveal(self, data):
        """Receive %REVEAL and reveal cell(s)."""

        cells = self._string_to_cells(data)
        wx.CallAfter(self.wxc.XMPPRevealCells, cells)


    def send_highlight(self, cells):
        """Highlight cell(s).

           %HIGHLIGHT x,y[;x,y;x,y...]  or %REVEAL * for board
        """

        self.send_message("%%HIGHLIGHT %s" % self._cells_to_string(cells))


    def recv_highlight(self, data):
        """Receive %HIGHLIGHT and highlight cell(s)."""

        cells = self._string_to_cells(data)
        wx.CallAfter(self.wxc.XMPPHighlight, cells)


    def send_disconnect(self, msg=""):
        """Disconnect. Sent by either party to end connection.

           %DISCONNECT <msg>
        """

        self.send_message("%%DISCONNECT %s" % msg)

        
    def recv_disconnect(self, data, mfrom):
        """Handle disconnection notice."""

        comment = 'Disconnect from %s: "%s"' % ( 
                mfrom, data or "Goodbye." )
        wx.CallAfter(self.wxc.XMPPShowComment, comment)

        # Drop this friend; if we have none left, disconnect
        del self.wxc.friends[mfrom]
        if not self.wxc.friends:
            wx.CallAfter(self.wxc.XMPPDisconnect, noecho=True)
