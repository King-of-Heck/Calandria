"""Open the viewer as an app window.

Microsoft Edge is on every Windows 11 machine (the work laptop included) and `msedge.exe
--app=URL` gives a window with no tabs and no address bar and its own taskbar entry, so the
viewer looks like a program rather than a web page. Without Edge, or if it fails to start, the
default browser opens the URL as an ordinary tab, as before.
"""
from __future__ import annotations

import os
import subprocess
import sys
import webbrowser

EDGE_RELATIVE = os.path.join("Microsoft", "Edge", "Application", "msedge.exe")
EDGE_ROOTS = ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")     # system x86, system x64, per-user


def edge_path(env=None) -> str | None:
    """The first msedge.exe under the usual install roots, or None."""
    env = os.environ if env is None else env
    for var in EDGE_ROOTS:
        root = env.get(var)
        if root:
            candidate = os.path.join(root, EDGE_RELATIVE)
            if os.path.isfile(candidate):
                return candidate
    return None


def open_viewer(url: str, env=None, popen=subprocess.Popen) -> str:
    """Open `url` as an Edge app window, else in the default browser; return "edge" or "browser".

    The child gets no handles from us (a log file must not be held open by Edge), and it is not
    waited on: when Edge is already running, msedge.exe hands the window to that process and
    exits at once, so its lifetime says nothing about the window's.
    """
    edge = edge_path(env)
    if edge is not None:
        try:
            popen([edge, f"--app={url}"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL)
            return "edge"
        except OSError as e:
            print("edge did not start:", ascii(str(e)), file=sys.stderr)
    webbrowser.open(url)
    return "browser"
