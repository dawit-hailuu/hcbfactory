"""
Simple file-based backup + restore.
Online database backup copy.
"""
import os
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime

from app.database.db import DB_PATH

def make_backup(out_path: str) -> str:
    """Write a snapshot of the live DB to `out_path`. Returns the path."""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(DB_PATH))
    dst = sqlite3.connect(out_path)
    try:
        src.backup(dst)  # SQLite online backup (safe even with open connections)
    finally:
        dst.close()
        src.close()
    return out_path

def default_backup_path() -> str:
    """A sensible default filename: <app>/backups/factory_backup_YYYY-MM-DD_HH-MM-SS.db"""
    backups_dir = DB_PATH.parent.parent / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return str(backups_dir / f"factory_backup_{stamp}.db")

def restore_backup(in_path: str):
    """Replace the live DB with the file at `in_path`."""
    if not os.path.exists(in_path):
        raise FileNotFoundError(in_path)

    # Quick sanity check: is the file a valid SQLite database with our tables?
    test = sqlite3.connect(in_path)
    try:
        rows = test.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r[0] for r in rows}
        required = {"users", "articles", "vouchers", "journal_entries", "inventory_ledger"}
        if not required.issubset(names):
            raise ValueError(
                f"Backup file is missing required tables. Found: {sorted(names)}"
            )
    finally:
        test.close()

    # Move the current DB aside before overwriting (rescue copy)
    if os.path.exists(DB_PATH):
        rescue = str(DB_PATH) + ".pre-restore"
        shutil.copy2(str(DB_PATH), rescue)

    shutil.copy2(in_path, str(DB_PATH))
    return str(DB_PATH)
