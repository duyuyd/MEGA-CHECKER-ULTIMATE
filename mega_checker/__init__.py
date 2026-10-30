"""MEGA CHECKER ULTIMATE — privacy-first email and domain diagnostics."""
import sys
from pathlib import Path

_VENDOR = Path(__file__).resolve().parent.parent / "vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

__version__ = "9.0.4"
APP_NAME = "MEGA CHECKER ULTIMATE"
