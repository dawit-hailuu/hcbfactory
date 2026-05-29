# MN Construction — Factory Manager

Offline desktop application for managing the MN Construction factory:
Hollow Concrete Blocks (HCB), Terazo tiles, and Pipes (ቱቦ).

100% offline. No server. No internet. Just install Python and run.

## What it does

- **Dashboard** — Revenue, Profit, Sales, Production, Low-stock. Click any card for today's details.
- **Inventory** — Materials with supplier + unit-cost tracking. Stock history with full searchable ledger.
- **Production** — Record runs with "Made by" worker, see live material-consumption preview, record damaged blocks. Admin can edit or delete past runs (audit-logged).
- **Bulk Entry** — Record several products at once, one row per product.
- **Sales** — Cash or partial-payment / credit sales. Print A5 receipt. Edit / delete with audit log.
- **Customers** — Per-customer balances, statement of account, receive payment.
- **Reports** — Per-category tabs (HCB / Terazo / Pipes), Profit & Loss, Waste, Material Usage, Finished Goods. Customer filter. Date filters or free range. PDF export.
- **Expenses** — Track Labor, Utilities, Rent, Transport, Maintenance, etc. Feeds Net Profit.
- **Products & Formulas** — Edit any formula, sell price, or product name. Formula changes are dated so old records stay accurate.
- **Tools** — Backup, restore, worker performance report.
- **Audit Log** — Every edit, delete, and notable action recorded.
- **Users** — Admin / worker roles.
- **Search bar** on every list/history view.
- **Dark mode** toggle.

## Setup

Python 3.9+.

```bash
pip install -r requirements.txt
python main.py
```

SQLite DB is auto-created at `data/factory.db`.

## Default login

```
username:  admin
password:  admin123
```

Change immediately from Users screen.

## Build a standalone .exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "MN Construction" main.py
```

Output: `dist/MN Construction.exe`. Hand over with an empty `data/` folder; the DB self-creates on first run.

## Critical: back up regularly

Tools → Backup Now. Save to USB or another drive at least weekly. Your entire database lives in one file (`data/factory.db`) so it's quick to back up.

## Notes

- Local time is used for all dates (no timezone bugs).
- Passwords are SHA-256 hashed.
- Schema migrations run automatically on startup. Existing data is preserved.
- Amharic in PDFs requires a system Ethiopic font (Nyala / Ebrima on Windows are auto-detected); without one, Amharic product names fall back to their codes.
