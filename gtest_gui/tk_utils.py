#!/usr/bin/env python3

# ------------------------------------------------------------------------ #
# Copyright (C) 2019,2023 Th. Zoerner
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

"""
Misc. helper functions for Tk
"""

import tkinter as tk
import tkinter.font as tkf

tk_top = None
font_normal = None
font_bold = None
font_content = None
font_content_bold = None
font_trace = None
wid_ctx_men = None

xselection_wid = None
xselection_txt = ""

def initialize(tk_arg):
    """ To be called once upon start-up for initialization. """
    global tk_top
    tk_top = tk_arg

    bind_classes()
    create_images()
    define_fonts()
    xselection_init()


def wid_exists(obj):
    """
    Helper function for safely checking if the given variable is a valid
    reference to a widget that has not yet been destroyed.
    """
    if obj is not None:
        try:
            obj.winfo_ismapped()
            return True
        except tk.TclError:
            pass
    return False


def safe_destroy(wid):
    """
    Destroy the widget referred to by the given variable and ignore any errors,
    such as reference being uninitialized or widget alredy destroyed.
    """
    try:
        wid.destroy()
    except tk.TclError:
        pass


def bind_call_and_break(func):
    """
    Helper function for use in callables registered to windowing events: The
    function will invoke the given callable and then return string "break",
    which informs the event handler to stop dispatching callbacks for this
    event, in case multiple callables are registered for it. This helper
    function is needed as Python lambdas can only contain a single expression.
    """
    func()
    return "break"


def get_context_menu_widget():
    """
    Helper function that returns a widget that can be used for a context menu.
    The returned widget is shared across all context menus, as only a single
    menu will be displayed at the same time. The previous menu content is
    cleared before returning from this function. The caller shall fill the menu
    newly from scratch every time it needs to be displayed. (If this is not
    wanted, it should use a dedicated menu widget instead.)
    """
    global wid_ctx_men
    if wid_exists(wid_ctx_men):
        wid_ctx_men.delete(0, "end")
    else:
        wid_ctx_men = tk.Menu(tk_top, tearoff=0)
    return wid_ctx_men


def post_context_menu(parent, xoff, yoff):
    """
    Helper function for "posting" (i.e. displaying) the default menu widget
    returned by get_context_menu_widget() at the given screen coordinates which
    are relative to the given widget's root coordinates.
    """
    global wid_ctx_men
    rootx = parent.winfo_rootx() + xoff
    rooty = parent.winfo_rooty() + yoff
    tk_top.tk.call("tk_popup", wid_ctx_men, rootx, rooty, 0)


def create_images():
    """
    Define images for use by various widgets. The images are defined centrally
    as they share a global namespace.
    """
    tk_top.call('image', 'create', 'bitmap', 'img_run', '-data',
                '#define img_width 12\n'
                '#define img_height 9\n'
                'static unsigned char img_bits[] = {\n'
                ' 0x1b, 0x00,'
                ' 0x3b, 0x00,'
                ' 0x7b, 0x00,'
                ' 0xfb, 0x00,'
                ' 0xfb, 0x01,'
                ' 0xfb, 0x00,'
                ' 0x7b, 0x00,'
                ' 0x3b, 0x00,'
                ' 0x1b, 0x00};')

    tk_top.call('image', 'create', 'bitmap', 'img_resume', '-data',
                '#define img_width 12\n'
                '#define img_height 9\n'
                'static unsigned char img_bits[] = {\n'
                ' 0x18, 0x00,'
                ' 0x38, 0x00,'
                ' 0x78, 0x00,'
                ' 0xf8, 0x00,'
                ' 0xf8, 0x01,'
                ' 0xf8, 0x00,'
                ' 0x78, 0x00,'
                ' 0x38, 0x00,'
                ' 0x18, 0x00};')

    tk_top.call('image', 'create', 'bitmap', 'img_stop', '-data',
                '#define img_width 12\n'
                '#define img_height 9\n'
                'static unsigned char img_bits[] = {\n'
                ' 0x00, 0x00,'
                ' 0xfe, 0x10,'
                ' 0xfe, 0x10,'
                ' 0xfe, 0x10,'
                ' 0xfe, 0x10,'
                ' 0xfe, 0x10,'
                ' 0xfe, 0x10,'
                ' 0xfe, 0x10,'
                ' 0x00, 0x00};')

    tk_top.call('image', 'create', 'bitmap', 'img_repeat', '-data',
                '#define img_width 12\n'
                '#define img_height 9\n'
                'static unsigned char img_bits[] = {\n'
                ' 0xfe, 0x01,'
                ' 0x01, 0x00,'
                ' 0x21, 0x00,'
                ' 0x61, 0x00,'
                ' 0xe1, 0x00,'
                ' 0xfe, 0x01,'
                ' 0xe0, 0x00,'
                ' 0x60, 0x00,'
                ' 0x20, 0x00};')

    tk_top.call('image', 'create', 'bitmap', 'img_drop_down', '-data',
                '#define img_width 15\n'
                '#define img_height 15\n'
                'static unsigned char img_bits[] = {\n'
                ' 0x00, 0x00,'
                ' 0x00, 0x00,'
                ' 0x00, 0x00,'
                ' 0x00, 0x00,'
                ' 0x00, 0x00,'
                ' 0xf8, 0x0f,'
                ' 0xf0, 0x07,'
                ' 0xe0, 0x03,'
                ' 0xc0, 0x01,'
                ' 0x80, 0x00,'
                ' 0x00, 0x00,'
                ' 0x00, 0x00,'
                ' 0x00, 0x00,'
                ' 0x00, 0x00,'
                ' 0x00, 0x00};')

    tk_top.call('image', 'create', 'bitmap', 'img_folder', '-data',
                '#define img_width 14\n'
                '#define img_height 5\n'
                'static unsigned char img_bits[] = {\n'
                ' 0x00, 0x00,'
                ' 0x00, 0x00,'
                ' 0x00, 0x00,'
                ' 0xd8, 0x06,'
                ' 0xd8, 0x06};')


def bind_classes():
    """
    This function is called upon start-up for defining event binding classes for
    use by various widgets.
    """
    text_modifier_events = (
        "<<Clear>>", "<<Cut>>", "<<Paste>>", "<<PasteSelection>>",
        "<<Redo>>", "<<Undo>>", "<<TkAccentBackspace>>", "<Key-BackSpace>",
        "<Key>", "<Key-Delete>", "<Key-Insert>", "<Key-Return>",
        # Not modifiers, but events are overridden below
        "<Key-Tab>", "<Control-Key-a>")

    # Define Read-Only Text key binding class:
    # Copy all event bindings of the Text widget, except for those that allow modifying content.
    for event in set(tk_top.bind_class("Text")) - set(text_modifier_events):
        tk_top.bind_class("TextReadOnly", event, tk_top.bind_class("Text", event))

    for class_name in ("TextReadOnly", "TextSel"):
        tk_top.bind_class(class_name, "<Key-Tab>", tk_top.bind_class("Text", "<Control-Key-Tab>"))

    for class_name in ("TextReadOnly", "Text", "Entry", "Listbox"):
        tk_top.bind_class(class_name, "<Control-Key-a>",
                          lambda e: e.widget.event_generate("<<SelectAll>>"))

    tk_top.bind_class("Listbox", "<Key-Home>", tk_top.bind_class("Listbox", "<Control-Key-Home>"))
    tk_top.bind_class("Listbox", "<Key-End>", tk_top.bind_class("Listbox", "<Control-Key-End>"))

    tk_top.bind_class("Button", "<Return>", tk_top.bind_class("Button", "<Key-Space>"))

    for event in ("<Button-2>", "<B2-Motion>", "<Key-Prior>", "<Key-Next>",
                  "<Shift-Key-Tab>", "<Control-Key-Tab>", "<Control-Shift-Key-Tab>"):
        tk_top.bind_class("TextSel", event, tk_top.bind_class("Text", event))

    # Bindings for scrolling text widget with the mouse wheel
    tk_top.bind_class("TextWheel", "<Button-4>", lambda e: e.widget.yview_scroll(-3, "units"))
    tk_top.bind_class("TextWheel", "<Button-5>", lambda e: e.widget.yview_scroll(3, "units"))
    tk_top.bind_class("TextWheel", "<MouseWheel>",
                      lambda e: e.widget.yview_scroll(e.delta * -3 // 120, "units"))

    for event in ("<Button-4>", "<Button-5>", "<MouseWheel>"):
        tk_top.bind_class("TextReadOnly", event, tk_top.bind_class("TextWheel", event))
        tk_top.bind_class("TextSel", event, tk_top.bind_class("TextWheel", event))


def define_fonts():
    """
    This function is called upon start-up for defining common fonts for use by
    various widgets. Font configuration initialized here is usually overridden
    immediately afterward when loading the configuration file.
    """
    global font_normal, font_bold, font_content, font_content_bold, font_trace

    # smaller font for the Tk message box
    tk_top.eval("option add *Dialog.msg.font {%s 10 bold}" % "TkDefaultFont")

    # fonts for text and label widgets
    font_normal = tkf.Font(font="TkDefaultFont")
    font_bold = font_normal.copy()
    font_content = tkf.Font(font="TkTextFont")
    font_content_bold = tkf.Font(font="TkTextFont")
    font_trace = tkf.Font(font="TkFixedFont")
    update_derived_fonts()


def update_derived_fonts():
    """
    When the user reconfigures fonts, the caller applies the new configuration
    directly to the respective font objects. This function needs to be called
    afterward for additionally updating derived fonts, namely the bold variants.
    """
    global font_normal, font_bold, font_content, font_content_bold
    opt = font_normal.configure()
    opt["weight"] = tkf.BOLD
    font_bold.configure(**opt)

    opt = font_content.configure()
    opt["weight"] = tkf.BOLD
    font_content_bold.configure(**opt)


def init_font_content(opt):
    """
    Create a font object with the given configuration parameters and assign it
    to the font variables used for displaying text in lists et.al. (Usually a
    proportional font is used here.)
    """
    global font_content, font_content_bold
    if font_content.configure() != opt:
        font_content = tkf.Font(**opt)

    opt["weight"] = tkf.BOLD
    font_content_bold.configure(**opt)


def init_font_trace(opt):
    """
    Create a font object with the given configuration parameters and assign it
    to the font variables used for displaying text from trace output files.
    (Usually a monospace font is used here.)
    """
    global font_trace
    if font_trace.configure() != opt:
        font_trace = tkf.Font(**opt)


#
# Clipboard helper functions
#

def xselection_init():
    """
    Initialize widgets required for managing the X11 selection (clipboard
    equivalent). Specifically the function creates a dummy widget that is later
    used for adding a handler which is called every time the window system wants
    to read the selection text.
    """
    global xselection_wid, xselection_txt
    xselection_txt = ""
    xselection_wid = tk.Label(tk_top)
    tk_top.call("selection", "handle", xselection_wid, tk_top.register(xselection_handler))


def xselection_handler(off, xlen):
    """
    Callback registered with X11, which is called for retrieving selection text.
    """
    try:
        off = int(off)
        xlen = int(xlen)
        return xselection_txt[off : (off + xlen)]
    except tk.TclError:
        return ""


def xselection_export(txt, to_clipboard):
    """
    Stores the given text internally and notifies X11 that the X11 selection now
    shall be owned by the application. If the user wants to paste the selection
    somewhere, the registered handler function will be invoked by X11 to
    retrieve the text.
    """
    global xselection_txt

    # Update X selection
    xselection_txt = txt
    xselection_wid.selection_own()

    if to_clipboard:
        tk_top.clipboard_clear()
        tk_top.clipboard_append(txt)
