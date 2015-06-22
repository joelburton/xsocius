"""Printing System."""

import textwrap
import logging

from xsocius.utils import NAME, URL
import wx
from xsocius.gui.board import PresentationBoardMixin

FONTSIZE = 10


class PrintMixin():
    """Adds print menu options to windows."""

    def __init__(self, *args, **kwargs):
        self.printer = PuzzlePrinter(self)

    def OnPrint(self, event):
        """Print."""

        self.printer.Print(self.puzzle)

    def OnPrintPreview(self, event):
        """Print prview."""

        self.printer.Preview(self.puzzle)

    def OnPrintSetup(self, event):
        """Print setup."""

        self.printer.PageSetup()


# ---- Printer Classes ----#

class PuzzlePrinter(object):
    """Manages PrintData and Printing"""

    def __init__(self, parent):
        self.parent = parent
        self.print_data = wx.PrintData()

        self.print_data.SetPaperId(wx.PAPER_LETTER)
        self.print_data.SetOrientation(wx.PORTRAIT)
        self.print_margins = (wx.Point(5, 5), wx.Point(5, 5))

    def CreatePrintout(self, puzzle):
        """Creates a printout object"""

        data = wx.PageSetupDialogData(self.print_data)
        return PuzzlePrintout(puzzle, data, self.print_margins)

    def PageSetup(self):
        """Show the PrinterSetup dialog"""
        # Make a copy of our print data for the setup dialog

        dlg_data = wx.PageSetupDialogData(self.print_data)

        dlg_data.SetDefaultMinMargins(True)
        dlg_data.SetMarginTopLeft(self.print_margins[0])
        dlg_data.SetMarginBottomRight(self.print_margins[1])

        print_dlg = wx.PageSetupDialog(self.parent, dlg_data)

        if print_dlg.ShowModal() == wx.ID_OK:
            # Update the printer data with the changes from
            # the setup dialog.
            newdata = dlg_data.GetPrintData()
            self.print_data = wx.PrintData(newdata)
            self.print_data.SetPaperId(dlg_data.GetPaperId())
            self.print_margins = (newdata.GetMarginTopLeft(),
                                  newdata.GetMarginBottomRight())
        print_dlg.Destroy()

    def Preview(self, puzzle):
        """Show the print preview"""

        printout = self.CreatePrintout(puzzle)
        printout2 = self.CreatePrintout(puzzle)
        preview = wx.PrintPreview(printout, printout2, self.print_data)
        preview.SetZoom(70)
        if preview.IsOk():
            pre_frame = wx.PreviewFrame(preview, self.parent, "Print Preview")
            # The default size of the preview frame
            # sometimes needs some help.
            dsize = wx.GetDisplaySize()
            width = self.parent.GetSize()[0]
            height = dsize.GetHeight() - 100
            pre_frame.SetInitialSize((width, height))
            pre_frame.Initialize()
            pre_frame.Show()
        else:
            # Error
            wx.MessageBox("Failed to create print preview",
                          "Print Error",
                          style=wx.ICON_ERROR | wx.OK)

    def Print(self, puzzle):
        """Prints the document"""

        pdd = wx.PrintDialogData(self.print_data)
        printer = wx.Printer(pdd)
        printout = self.CreatePrintout(puzzle)
        result = printer.Print(self.parent, printout)

        if result:
            # Store copy of print data for future use
            dlg_data = printer.GetPrintDialogData()
            newdata = dlg_data.GetPrintData()
            self.print_data = wx.PrintData(newdata)

        elif printer.GetLastError() == wx.PRINTER_ERROR:
            wx.MessageBox("Printer error detected.",
                          "Printer Error",
                          style=wx.ICON_ERROR | wx.OK)
        printout.Destroy()


class PuzzlePrintout(wx.Printout, PresentationBoardMixin):
    """Creates an printout of a puzzle"""

    printout = True

    def __init__(self, puzzle, data, margins):
        super(PuzzlePrintout, self).__init__()

        # Attributes
        self.puzzle = puzzle
        self.data = data
        self.margins = margins

        self.rects = [[wx.Rect()
                       for y in range(puzzle.height)]
                      for x in range(puzzle.width)]

    def GetPageInfo(self):
        """Get the page range information"""

        # min, max, from, to # we only support 1 page
        return (1, 1, 1, 1)

    def HasPage(self, page):
        """Is a page within range"""

        return page <= 1

    def CalculateScale(self, dc):
        """Calculate scale between printout / screen."""

        # Scale the DC such that the printout is roughly the same as
        # the screen scaling.
        ppiPrinterX, ppiPrinterY = self.GetPPIPrinter()
        ppiScreenX, ppiScreenY = self.GetPPIScreen()
        logScale = float(ppiPrinterX) / float(ppiScreenX)

        logging.debug("printer ppi=%s,%s", ppiPrinterX, ppiPrinterY)
        logging.debug("screen ppi=%s, %s", ppiScreenX, ppiScreenY)
        logging.debug("logScale=%s", logScale)

        # Now adjust if the real page size is reduced (such as when
        # drawing on a scaled wx.MemoryDC in the Print Preview.)  If
        # page width == DC width then nothing changes, otherwise we
        # scale down for the DC.
        pw, ph = self.GetPageSizePixels()
        dw, dh = dc.GetSize()
        scale = logScale * float(dw) / float(pw)

        # Set the DC's scale.
        dc.SetUserScale(scale, scale)
        logging.debug("pw=%s, ph=%s, dw=%s, dh=%s, scale=%s",
                      pw, ph, dw, dh, scale)

        # Find the logical units per millimeter (for calculating the
        # margins)
        self.logUnitsMM = float(ppiPrinterX) / (logScale * 25.4)
        logging.debug("logUnitsMM=%s", self.logUnitsMM)

    def CalculateLayout(self, dc):
        """Calculate layout of page."""

        # Determine the position of the margins and the
        # page/line height
        topLeft, bottomRight = self.margins
        dw, dh = dc.GetSize()
        self.x1 = topLeft.x * self.logUnitsMM
        self.y1 = topLeft.y * self.logUnitsMM
        self.x2 = dc.DeviceToLogicalXRel(dw) - bottomRight.x * self.logUnitsMM
        self.y2 = dc.DeviceToLogicalYRel(dh) - bottomRight.y * self.logUnitsMM
        logging.debug("x1=%s, y1=%s, x2=%s, y2=%s",
                      self.x1, self.x2, self.y1, self.y2)

        # use a 1mm buffer around the inside of the box, and a few
        # pixels between each line
        self.pageHeight = self.y2 - self.y1 - 2 * self.logUnitsMM
        font = wx.Font(FONTSIZE, wx.TELETYPE, wx.NORMAL, wx.NORMAL)
        dc.SetFont(font)
        self.lineHeight = dc.GetCharHeight()
        self.linesPerPage = int(self.pageHeight / self.lineHeight)

    def _clue_fill(self, clues, direction, maxchar):
        """Fill clue text boxes."""

        out = []
        tw = textwrap.TextWrapper(width=maxchar, subsequent_indent="   ")
        for c in clues:
            out.append(tw.fill("%s. %s" % (c.num, getattr(c, direction))))
        return out

    def OnPrintPage(self, page):
        """Scales and Renders the bitmap
        to a DC and prints it
        """

        dc = self.GetDC()  # Get Device Context to draw on
        self.CalculateScale(dc)
        self.CalculateLayout(dc)

        w = (self.x2 - self.x1) * .65
        h = (self.y2 - self.y1) * .65
        w, h = min(w, h), min(w, h)

        # The hard numbers below were calculated using the Mac
        # logical page size for US letter (576 across). 
        # On Windows, this is bigger--so the numbers accordingly.

        FUDGE = self.GetLogicalPageRect()[2] / 576.0
        logging.debug("fudge factor=%s", FUDGE)

        TITLE_HEIGHT = 30 * FUDGE
        dc.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.BOLD))
        dc.DrawText(self.puzzle.title, self.x1, self.y1)
        dc.SetFont(wx.Font(6.5, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.NORMAL))
        dc.DrawText(self.puzzle.copyright, self.x1, self.y1 + 15 * FUDGE)

        self.PrepareDrawSizing(w, h, self.x1, self.y1 + TITLE_HEIGHT)
        self.setupColors()

        self.DrawBoard(dc)

        CLUETOP = self.y1 + h + TITLE_HEIGHT + 15 * FUDGE
        CLUERIGHT = self.x1 + w + 18 * FUDGE

        clues = self.puzzle.clues

        # Find a decent clue text size
        # XXX use font scale, also in more places?
        if wx.Platform == "__WXMSW__":
            fontsize = 4.5 + 240 / len(clues)
        else:
            # fontsize = 5 + 240 / len(clues)
            # Found some puzzles with longer clues, adjusted estimate
            fontsize = 5 + 170 / len(clues)
        maxchar = 310 / fontsize

        ac = [c for c in clues[1:] if c.across]
        split = len(ac) // 2
        across1 = self._clue_fill(ac[:split], 'across', maxchar)
        across2 = self._clue_fill(ac[split:], 'across', maxchar)

        down = self._clue_fill([c for c in clues[1:] if c.down],
                               'down', maxchar)
        down = down + ["\n\nPrintout by %s\n%s" % (NAME, URL)]

        dc.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.BOLD))
        dc.DrawText("Across  Clues", self.x1, CLUETOP)
        dc.DrawText("Down Clues", CLUERIGHT, self.y1)

        dc.SetFont(wx.Font(fontsize,
                           wx.FONTFAMILY_DEFAULT,
                           wx.NORMAL,
                           wx.NORMAL))
        self.lineHeight = dc.GetCharHeight()
        self._draw_text(dc, across1, self.x1, CLUETOP + 15 * FUDGE)
        self._draw_text(dc, across2, self.x1 + 170 * FUDGE, CLUETOP)
        self._draw_text(dc, down, CLUERIGHT, self.y1 + 15 * FUDGE)

        return True

    def _draw_text(self, dc, clues, x, y):
        """Draw text on printout."""

        for clue in clues:
            for line in clue.split("\n"):
                dc.DrawText(line, x, y)
                y += self.lineHeight

            # Add a little spacing between clues.
            y += 1
