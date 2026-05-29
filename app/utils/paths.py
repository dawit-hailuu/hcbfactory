"""
All file-system paths used by the app.

CRITICAL: paths are computed from this module's __file__, NOT from
Path.cwd(). When the app runs as a .exe launched from a Start-menu
shortcut, Windows sets cwd to C:\\Windows\\System32 — anything written
to cwd-relative paths fails with WinError 5 (Access Denied).

By anchoring to __file__ we always write next to the app folder, where
the user has full write access.
"""
import sys
from pathlib import Path


def _app_base() -> Path:
    """Folder containing the executable (or the project root in dev)."""
    if getattr(sys, "frozen", False):
        # PyInstaller-frozen .exe — sys.executable points to the .exe
        return Path(sys.executable).resolve().parent
    # Dev mode: this file is at app/utils/paths.py, so go up two levels
    return Path(__file__).resolve().parent.parent.parent


BASE       = _app_base()
DATA_DIR   = BASE / "data"
EXPORTS    = BASE / "exports"
RECEIPTS   = BASE / "receipts"
VOUCHERS   = BASE / "vouchers"
BACKUPS    = BASE / "backups"
ACCOUNTING = BASE / "accounting_exports"


def ensure_all():
    """Create all writable folders at startup so the user never sees
    'access denied' errors mid-flow."""
    for p in (DATA_DIR, EXPORTS, RECEIPTS, VOUCHERS, BACKUPS, ACCOUNTING):
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Some sandboxed environments forbid even this; we'll handle
            # the error gracefully when the user tries to save.
            pass
