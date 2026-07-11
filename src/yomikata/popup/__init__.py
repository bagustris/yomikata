"""Popup rendering and windowing.

Forces the X11 (XWayland) GDK backend before any submodule can import
``gi.repository.Gtk`` -- GDK locks in its backend as soon as Gtk is first
imported, so this must happen here, in the package's own __init__, rather
than in whichever of window.py/renderer.py happens to be imported first.
See window.py for why X11/XWayland is required at all: native Wayland
gives clients no way to position a window at an arbitrary screen
coordinate, which this app's popup fundamentally needs to do.
"""

import os

os.environ.setdefault("GDK_BACKEND", "x11")
