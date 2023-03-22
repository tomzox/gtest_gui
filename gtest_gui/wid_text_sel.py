#!/usr/bin/env python3

import gtest_gui.tk_utils as tk_utils

# ------------------------------------------------------------------------ #
# Copyright (C) 2007-2010,2019-2023 Th. Zoerner
# ------------------------------------------------------------------------ #
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------ #

# This code is copied from Trace Browser (trowser.py)
#
# The following class allows using a text widget in the way of a listbox, i.e.
# allowing to select one or more lines. The mouse bindings are similar to the
# listbox "extended" mode. The cursor key bindings differ from the listbox, as
# there is no "active" element (i.e. there's no separate cursor from the
# selection.)
#
# Member variables:
# - text widget whose selection is managed by the class instance
# - callback to invoke after selection changes
# - callback which provides the content list length
# - ID of "after" event handler while scrolling via mouse, or None
# - scrolling speed
# - anchor element index OR last selection cursor pos
# - list of indices of selected lines (starting at zero)
#
class Text_sel_wid(object):
    #
    # This constructor is called after a text widget is created for initializing
    # all member variables and for adding key and mouse event bindings for
    # handling the selection.
    #
    def __init__(self, wid, cb_proc, len_proc, mode="extended"):
        self.wid = wid
        self.cb_proc = cb_proc
        self.len_proc = len_proc
        self.scroll_tid = None
        self.scroll_speed = 0
        self.anchor_idx = -1
        self.sel = []

        self.wid.bind("<Control-ButtonPress-1>", lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_pick(e.x, e.y)))
        self.wid.bind("<Shift-ButtonPress-1>", lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_resize(e.x, e.y)))
        self.wid.bind("<ButtonPress-1>",   lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_button(e.x, e.y)))
        self.wid.bind("<ButtonRelease-1>", lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_motion_end()))
        if mode == "browse":
            self.wid.bind("<B1-Motion>",    lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_button(e.x, e.y)))
        else:
            self.wid.bind("<B1-Motion>",    lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_motion(e.x, e.y)))

        self.wid.bind("<Shift-Key-Up>",   lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_key_resize(-1)))
        self.wid.bind("<Shift-Key-Down>", lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_key_resize(1)))
        self.wid.bind("<Key-Up>",         lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_key_up_down(-1)))
        self.wid.bind("<Key-Down>",       lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_key_up_down(1)))
        self.wid.bind("<Shift-Key-Home>", lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_key_home_end(False, True)))
        self.wid.bind("<Shift-Key-End>",  lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_key_home_end(True, True)))
        self.wid.bind("<Key-Home>",       lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_key_home_end(False, False)))
        self.wid.bind("<Key-End>",        lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_key_home_end(True, False)))

        self.wid.bind("<Control-Key-a>", lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_select_all()))
        self.wid.bind("<Control-Key-c>", lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.text_sel_copy_clipboard(True)))

        self.wid.bind("<Key-Prior>", lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_key_page_up_down(-1)))
        self.wid.bind("<Key-Next>",  lambda e, self=self: tk_utils.bind_call_and_break(lambda: self.__text_sel_key_page_up_down(1)))


    #
    # This is an interface function which allows outside users to retrieve a
    # list of selected elements (i.e. a list of indices)
    #
    def text_sel_get_selection(self):
        return self.sel


    #
    # This is an interface function which allows to modify the selection
    # externally.
    #
    def text_sel_set_selection(self, sel, do_callback=True):
        if len(sel) > 0:
            self.anchor_idx = sel[0]
        self.sel = sel

        self.text_sel_show_selection()

        if do_callback:
            self.cb_proc(self.sel)


    #
    # This is an interface function which is used by context menus to check
    # if the item under the mouse pointer is included in the selection.
    # If not, the selection is set to consist only of the pointed item.
    #
    def text_sel_context_selection(self, xcoo, ycoo):
        line = self.__text_sel_coo2_line(xcoo, ycoo)
        if line != -1:
            if len(self.sel) != 0:
                if not line in self.sel:
                    # click was outside the current selection -> replace selection
                    self.text_sel_set_selection([line])
            else:
                # nothing selected yet -> select element under the mouse pointer
                self.text_sel_set_selection([line])
        else:
            self.text_sel_set_selection([])


    #
    # This function is bound to button-press events in the text widget while
    # neither Control nor Shift keys are pressed.  A previous selection is
    # is cleared and the entry below the mouse (if any) is selected.
    #
    def __text_sel_button(self, xcoo, ycoo):
        line = self.__text_sel_coo2_line(xcoo, ycoo)
        old_sel = self.sel
        if (line >= 0) and (line < self.len_proc()):
            # select the entry under the mouse pointer
            self.anchor_idx = line
            self.sel = [line]
            notify = True
        else:
            # mouse pointer is not above a list entry -> clear selection
            self.sel = []
            notify = False

        # update display if the selection changed
        if old_sel != self.sel:
            self.text_sel_show_selection()
            notify = True

        # invoke notification callback if an element was selected or de-selected
        if notify:
            self.cb_proc(self.sel)

        self.wid.focus_set()


    #
    # This function is bound to mouse pointer motion events in the text widget
    # while the mouse button is pressed down. This allows changing the extent
    # of the selection. The originally selected item ("anchor") always remains
    # selected.  If the pointer is moved above or below the widget borders,
    # the text is scrolled.
    #
    def __text_sel_motion(self, xcoo, ycoo):
        # the anchor element is the one above which the mouse button was pressed
        # (the check here is for fail-safety only, should always be fulfilled)
        if self.anchor_idx >= 0:
            wh = self.wid.winfo_height()
            # check if the mouse is still inside of the widget area
            if (ycoo >= 0) and (ycoo < wh):
                # identify the item under the mouse pointer
                line = self.__text_sel_coo2_line(xcoo, ycoo)
                if line != -1:
                    # build list of all consecutive indices between the anchor and the mouse position
                    sel = Text_sel_wid.__idx_range(self.anchor_idx, line)
                    # update display and invoke notification callback if the selection changed
                    if sel != self.sel:
                        self.sel = sel
                        self.text_sel_show_selection()
                        self.cb_proc(self.sel)

                # cancel scrolling timer, as the mouse is now back inside the widget
                if self.scroll_tid is not None:
                    tk_utils.tk_top.after_cancel(self.scroll_tid)
                    self.scroll_tid = None

            else:
                # mouse is outside of the text widget - start scrolling
                # scrolling speed is determined by how far the mouse is outside
                fh = tk_utils.tk_top.call("font", "metrics", self.wid.cget("font"), "-linespace")
                if ycoo < 0:
                    delta = 0 - ycoo
                else:
                    delta = ycoo - wh

                delay = 500 - delta * 100 // fh
                if (delay > 500): delay = 500
                if (delay <  50): delay =  50
                if self.scroll_tid is None:
                    # start timer and remember it's ID to be able to cancel it later
                    delta = -1 if (ycoo < 0) else 1
                    self.scroll_tid = tk_utils.tk_top.after(delay, lambda: self.__text_sel_motion_scroll(delta))
                    self.scroll_delay = delay
                else:
                    # timer already active - just update the delay
                    self.scroll_delay = delay


    #
    # This timer event handler is activated when the mouse is moved outside of
    # the text widget while the mouse button is pressed. The handler re-installs
    # itself and is only stopped when the button is released or the mouse is
    # moved back inside the widget area.  The function invariably scrolls the
    # text by one line. Scrolling speed is varied by means of the delay time.
    #
    def __text_sel_motion_scroll(self, delta):
        # scroll up or down by one line
        self.wid.yview_scroll(delta, "units")

        # extend the selection to the end of the viewable area
        if delta < 0:
            self.__text_sel_motion(0, 0)
        else:
            self.__text_sel_motion(0, self.wid.winfo_height() - 1)

        # install the timer again (possibly with a changed delay if the mouse was moved)
        self.scroll_tid = tk_utils.tk_top.after(self.scroll_speed, lambda: self.__text_sel_motion_scroll(delta))


    #
    # This function is boud to mouse button release events and stops a
    # possible on-going scrolling timer.
    #
    def __text_sel_motion_end(self):
        if self.scroll_tid is not None:
            tk_utils.tk_top.after_cancel(self.scroll_tid)
            self.scroll_tid = None


    #
    # This function is bound to mouse button events while the Control key is
    # pressed. The item below the mouse pointer is toggled in the selection.
    # Otherwise the selection is left unchanged.  Note this operation always
    # clears the "anchor" element, i.e. the selection cannot be modified
    # using "Shift-Click" afterwards.
    #
    def __text_sel_pick(self, xcoo, ycoo):
        line = self.__text_sel_coo2_line(xcoo, ycoo)
        if line != -1:
            # check if the item is already selected
            try:
                pick_idx = self.sel.index(line)
                # already selected -> remove from selection
                del self.sel[pick_idx]
            except:
                pick_idx = -1
                self.sel.append(line)

            if len(self.sel) <= 1:
                self.anchor_idx = line

            self.text_sel_show_selection()
            self.cb_proc(self.sel)


    #
    # This function is bound to mouse button events while the Shift key is
    # pressed. The selection is changed to cover all items starting at the
    # anchor item and the item under the mouse pointer.  If no anchor is
    # defined, the selection is reset and only the item under the mouse is
    # selected.
    #
    def __text_sel_resize(self, xcoo, ycoo):
        line = self.__text_sel_coo2_line(xcoo, ycoo)
        if line != -1:
            if self.anchor_idx != -1:
                self.sel = Text_sel_wid.__idx_range(self.anchor_idx, line)
                self.text_sel_show_selection()
                self.cb_proc(self.sel)
            else:
                self.__text_sel_button(xcoo, ycoo)


    #
    # This function is bound to the page up/down cursor keys.
    #
    def __text_sel_key_page_up_down(self, delta):
        content_len = self.len_proc()
        if content_len == 0:
            return

        if (delta < 0) and (self.wid.bbox("1.0") is not None):
            self.__text_sel_select_line(0)

        elif (delta > 0) and (self.wid.bbox("%d.0" % content_len) is not None):
            self.__text_sel_select_line(content_len - 1)

        else:
            if self.sel:
                prev_line = min(self.sel) if delta < 0 else max(self.sel)
            else:
                prev_line = -1

            self.wid.yview("scroll", delta, "pages")

            line = self.__text_sel_coo2_line(1, self.wid.winfo_height() / 2)
            if line != -1:
                if delta < 0 and line > prev_line and prev_line != -1:
                    line = prev_line
                if delta > 0 and line < prev_line:
                    line = prev_line

                # set selection on the new line
                self.__text_sel_select_line(line)


    #
    # This function is bound to the up/down cursor keys. If no selection
    # exists, the viewable first item in cursor direction is selected.
    # If a selection exists, it's cleared and the item next to the
    # previous selection in cursor direction is selected.
    #
    def __text_sel_key_up_down(self, delta):
        content_len = self.len_proc()
        if content_len > 0:
            sel = sorted(self.sel)
            if len(sel) != 0:
                # selection already exists -> determine item below or above
                if delta < 0:
                    line = sel[0]
                else:
                    line = sel[-1]

                # determine the newly selected item
                line += delta

                if (line >= 0) and (line < content_len):
                    # set selection on the new line
                    self.__text_sel_select_line(line)

                elif len(sel) > 1:
                    # selection already includes last line - restrict selection to this single line
                    if delta < 0:
                        line = 0
                    else:
                        line = content_len - 1

                    self.__text_sel_select_line(line)

            else:
                # no selection exists yet -> use last anchor, or top/bottom visible line
                if ((self.anchor_idx >= 0) and
                    (self.wid.bbox("%d.0" % (self.anchor_idx + 1)) is not None)):
                    idx = "%d.0" % (self.anchor_idx + 1)
                else:
                    if delta > 0:
                        idx = "@1,1"
                    else:
                        idx = "@1,%d" % (self.wid.winfo_height() - 1)

                pos = self.wid.index(idx)
                if pos != "":
                    line = int(pos.split(".")[0])
                    if line > 0:
                        line -= 1
                        if line >= content_len:
                            line = content_len - 1
                        self.__text_sel_select_line(line)


    #
    # This function is bound to the up/down cursor keys while the Shift key
    # is pressed. The selection is changed to cover all items starting at the
    # anchor item and the next item above or below the current selection.
    #
    def __text_sel_key_resize(self, delta):
        content_len = self.len_proc()
        if len(self.sel) > 0:
            sel = sorted(self.sel)
            # decide if we manipulate the upper or lower end of the selection:
            # use the opposite side of the anchor element
            if self.anchor_idx == sel[-1]:
                line = sel[0]
            else:
                line = sel[-1]

            line += delta
            if (line >= 0) and (line < content_len):
                self.sel = Text_sel_wid.__idx_range(self.anchor_idx, line)

                self.text_sel_show_selection()
                self.wid.see("%d.0" % (line + 1))
                self.cb_proc(self.sel)

        else:
            self.__text_sel_key_up_down(delta)


    #
    # This function is bound to the "Home" and "End" keys.  While the Shift
    # key is not pressed, the first or last element in the list are selected.
    # If the Shift key is pressed, the selection is extended to include all
    # items between the anchor and the first or last item.
    #
    def __text_sel_key_home_end(self, is_end, is_resize):
        content_len = self.len_proc()
        if content_len > 0:
            if is_end:
                line = content_len - 1
            else:
                line = 0

            if not is_resize:
                self.anchor_idx = line
                self.sel = [line]
            else:
                if self.anchor_idx >= 0:
                    self.sel = Text_sel_wid.__idx_range(self.anchor_idx, line)

            self.text_sel_show_selection()
            self.wid.see("%d.0" % (line + 1))
            self.cb_proc(self.sel)


    #
    # This function is bound to the "CTRL-A" key to select all entries in
    # the list.
    #
    def __text_sel_select_all(self):
        content_len = self.len_proc()
        if content_len > 0:
            self.sel = Text_sel_wid.__idx_range(0, content_len - 1)

            self.text_sel_show_selection()
            self.cb_proc(self.sel)


    #
    # This helper function is used to build a list of all indices between
    # (and including) two given values in increasing order.
    #
    def __idx_range(start, end):
        if start > end:
            return list(range(end, start + 1))
        else:
            return list(range(start, end + 1))


    #
    # This interface function displays a selection in the text widget by adding
    # the "sel" tag to all selected lines. (Note the view is not affected, i.e.
    # the selection may be outside of the viewable area.)
    #
    def text_sel_show_selection(self):
        # first remove any existing highlight
        self.wid.tag_remove("sel", "1.0", "end")

        # select each selected line (may be non-consecutive)
        for line in self.sel:
            self.wid.tag_add("sel", "%d.0" % (line + 1), "%d.0" % (line + 2))

        if (len(self.sel) == 0) or (self.anchor_idx == -1):
            self.wid.mark_set("insert", "end")
        else:
            self.wid.mark_set("insert", "%d.0" % (self.anchor_idx + 1))


    #
    # This function changes the selection to the single given line.
    #
    def __text_sel_select_line(self, line):
        self.anchor_idx = line
        self.sel = [line]

        self.text_sel_show_selection()
        self.wid.see("%d.0" % (line + 1))
        self.cb_proc(self.sel)


    #
    # This function determines the line under the mouse pointer.
    # If the pointer is not above a content line, -1 is returned.
    #
    def __text_sel_coo2_line(self, xcoo, ycoo):
        pos = self.wid.index("@%d,%d" % (xcoo,ycoo))
        if pos != "":
            line = int(pos.split(".")[0]) - 1
            if (line >= 0) and (line < self.len_proc()):
                return line
        return -1


    #
    # This function has to be called when an item has been inserted into the
    # list to adapt the selection: Indices following the insertion are
    # incremented.  The new element is not included in the selection.
    #
    def text_sel_adjust_insert(self, line):
        self.sel = [(x if x < line else x+1) for x in self.sel]

        if self.anchor_idx >= line:
            self.anchor_idx += 1


    #
    # This function has to be called when an item has been deleted from the
    # list (asynchronously, i.e. not via a command related to the selection)
    # to adapt the list of selected lines: The deleted line is removed from
    # the selection (if included) and following indices are decremented.
    #
    def text_sel_adjust_deletion(self, line):
        self.sel = [(x if x < line else x-1) for x in self.sel if x != line]

        if self.anchor_idx > line:
            self.anchor_idx -= 1

    #
    # This handler is bound to CTRL-C in the selection and performs <<Copy>>
    # (i.e. copies the content of all selected lines to the clipboard.)
    #
    def text_sel_copy_clipboard(self, to_clipboard):
        msg = "".join([self.wid.get("%d.0" % (line + 1), "%d.0" % (line + 2)) for line in self.sel])
        tk_utils.xselection_export(msg, to_clipboard)
