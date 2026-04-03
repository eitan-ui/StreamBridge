import os
import sys


def _read_version() -> str:
    """Read version from VERSION file, checking frozen and source paths."""
    bases = [os.path.dirname(os.path.abspath(__file__))]
    if getattr(sys, "frozen", False):
        bases.insert(0, getattr(sys, "_MEIPASS", ""))
    for base in bases:
        vf = os.path.join(base, "VERSION")
        if os.path.isfile(vf):
            with open(vf) as f:
                return f.read().strip()
    return "0.0.0"


VERSION = _read_version()
APP_NAME = "StreamBridge"
