"""Adds game timer to puzzle window."""

import logging

import wx


class TimerButton(wx.ToggleButton):
    """Timer button at bottom of board."""

    def __init__(self, parent):
        wx.ToggleButton.__init__(self, parent, wx.ID_ANY, "0:00")
        self.Bind(wx.EVT_TOGGLEBUTTON, self.OnToggle)
        self.puzzle_window = self.GetTopLevelParent()
        #self.SetCanFocus(False) 
        self.Bind(wx.EVT_SET_FOCUS, self.IHaveFocus)

    def IHaveFocus(self, event):
        """Clue has focus, move to board."""

        logging.debug("Timer moving focus back to board")
        self.puzzle_window.board.SetFocus()

    def OnToggle(self, event):
        """Toggle button."""

        if self.GetValue():
            self.puzzle_window.start_timer()
        else:
            self.puzzle_window.stop_timer()

    def update(self, secs):
        """Update button; called every second."""

        mins = secs // 60
        secs = secs % 60
        
        self.SetLabel("%d:%0.2d" % (mins, secs))


class GameTimerMixin():
    """Time for solving puzzle."""

    def __init__(self, timer_start, start):
        self.puzzle.timer_time = timer_start
        self.puzzle.timer_running = start
        self.wxtimer = wx.Timer(self, wx.ID_ANY)
        self.Bind(wx.EVT_TIMER, self.OnTimer)
        self.timer_button.update(timer_start)

        if start or wx.GetApp().config.timer_autostart:
            self.start_timer()
            self.timer_button.SetValue(True)

    def start_timer(self):
        """Start timer."""

        self.wxtimer.Start(1000) # 1000ms=1 sec
        self.puzzle.timer_running = True
        self.timer_button.SetValue(True)
        self.GetMenuBar().FindItemById(self.ID_TIMER_TOGGLE).SetText("Pause Timer\tCtrl-T")

    def stop_timer(self):
        """Stop timer."""

        self.wxtimer.Stop()
        self.puzzle.timer_running = False
        self.timer_button.SetValue(False)
        self.GetMenuBar().FindItemById(self.ID_TIMER_TOGGLE).SetText("Restart Timer\tCtrl-T")

    def OnTimer(self, event):
        """Called every second."""

        self.puzzle.timer_time += 1
        self.timer_button.update(self.puzzle.timer_time)

    def OnTimerToggle(self, event):
        """Toggle Timer."""

        if self.puzzle.timer_running:
            self.stop_timer()
        else:
            self.start_timer()

    def OnTimeClear(self, event):
        """Clear timer."""

        self.puzzle.timer_time = 0
        self.timer_button.update(self.puzzle.timer_time)
