# MN Construction — Factory Manager

Offline desktop application for managing the MN Construction factory:
Hollow Concrete Blocks (HCB), Terazo tiles, and Pipes (ቱቦ).

100% offline. No server. No internet. Just install Python and run.

## What it does

- **Inventory** — Cement, Sand, Pumice, TeTer00, TeTer01, ቀለም, Water. Add stock, adjust stock, full history with search.
- **Production** — Pick a product, enter quantity, record who made it (with autocomplete), system computes material consumption from the active formula, deducts raw materials, adds finished goods. All atomic.
- **Sales** — Record sales with customer name and price. Auto-decrements finished stock. Searchable history.
- **Dashboard** — Today's revenue, sales count, production count, low-stock alerts. **Click any card** for detailed popup.
- **Reports** — Per-category breakdown (HCB / Terazo / Pipes); date filters (Today/Week/Month/Year/All Time/Custom); customer filter (answer "how much did we sell to Mr X between dates"); PDF export with Amharic font support.
- **Products & Formulas** — Admin can edit any product's formula and sell price from the UI. **Nothing is hardcoded** — formulas live in the database. Formula changes are versioned by date so old production records stay accurate.
- **Users** — Admin and worker roles. Admin manages users; workers can't see admin-only screens.
- **Dark mode** — toggle from the sidebar.
- **Global search** — every history/list view has a case-insensitive search box.

## Setup (one time)

Requires Python 3.9+.

```bash
pip install -r requirements.txt
python main.py
```

SQLite database is auto-created at `data/factory.db` on first run with all materials, products, and formulas seeded.

## Default login

```
username:  admin
password:  admin123
```

**Change this immediately** from the Users screen.

## Pre-loaded products

### HCB (per piece)
HCB10N, HCB10B, HCB10C, HCB15N, HCB15B, HCB15C, HCB20N, HCB20B, HCB20C, SLAB24, SLAB16, **HCBገተር** (new).
N-variants (HCB10N/15N/20N) use only Cement + Pumice.

### Terazo (per m²)
15×30×5, 30×30×5, 10×20×5, 20×20×5, 40×40×5, I-Section, C-Section.

### Pipes / ቱቦ (per piece) — NEW
ቱቦ ባለ 30, 40, 50, 60, 100, ቢረት 100.
Use only Cement + TeTer00.

> ⚠ TUBO_40 teter00=52.38288 is unusually large compared to siblings. Verify and edit via Products > Formula if wrong.

## Project structure

```
hcb_factory/
├── main.py
├── requirements.txt
├── CHANGELOG.md
├── data/
│   └── factory.db
├── exports/
└── app/
    ├── database/
    │   ├── db.py            # Schema + migrations
    │   └── seed.py          # Materials, products, formulas
    ├── services/            # All business logic
    │   ├── auth_service.py
    │   ├── inventory_service.py
    │   ├── product_service.py
    │   ├── production_service.py
    │   ├── sales_service.py
    │   └── report_service.py
    ├── ui/
    │   ├── login_window.py
    │   ├── main_window.py
    │   ├── views/
    │   │   ├── dashboard_view.py
    │   │   ├── inventory_view.py
    │   │   ├── production_view.py
    │   │   ├── sales_view.py
    │   │   ├── products_view.py
    │   │   ├── reports_view.py
    │   │   └── users_view.py
    │   └── widgets/
    │       ├── stat_card.py
    │       └── search_box.py
    └── utils/
        ├── clock.py
        └── theme.py
```

## Daily workflow

1. Open the app, check the Dashboard.
2. Click any stat card for today's details.
3. Add raw materials when shipments arrive: Inventory → Add Stock.
4. Record production: Production → pick product → enter quantity → enter "Made by" → preview → Confirm.
5. Record sales: Sales → New Sale.
6. End of period: Reports → pick period → optionally filter by customer → Export PDF.

## Editing formulas

Admin → Products → click **Formula** on any row. Numbers take effect from today; old records keep their old formula.

## Building a Windows .exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "MN Construction" main.py
```

Output: `dist/MN Construction.exe`. Hand over with an empty `data/` folder; the DB self-creates on first run.

## Notes

- Database is a single file: `data/factory.db`. Back up by copying it.
- Passwords are SHA-256 hashed.
- Local time is used everywhere (no UTC bugs near midnight).
- Migrations run automatically on startup — no manual database surgery needed for the v2 upgrade.
