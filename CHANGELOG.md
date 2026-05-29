# Changelog

## v3.1.0 — Extended Operational & Financial Features (2026-05-29)

1. **Customers & Accounts Receivable Workspace**
   - Developed a customer ledger tracker (`customers_view.py`) driven by Accounts Receivable (`GL-1105 Accounts Receivable`) general ledger postings.
   - Implemented dynamic debit/credit timeline statements of account for credit customer history.
   - Refactored debt collection to post balanced Cash Receipt Vouchers (CRVs) debiting Cash/Bank and crediting Accounts Receivable, with support for mobile payments.

2. **Operating Expenses Module**
   - Created a comprehensive expenses tracker (`expenses_view.py`) for tracking labor, utilities, rent, transport, and operating costs.
   - Refactored expense posting to generate Expense Vouchers (EVs) debiting Operating Expenses (`GL-5101 Operating Expenses`) and crediting Cash on Hand (`GL-1101 Cash on Hand`).
   - Integrated full transactional reversal voids and deleted record trails via supervisor UAC nodes.

3. **Dual-Compatible Partial Deposit Sales**
   - Refactored the double-entry sales posting engine (`sales_service.py`) to handle partial cash payments and deposit splits.
   - Automatically posts general ledger debit splits between Cash on Hand and Accounts Receivable depending on the customer's payment deposit, with full backward compatibility for `payment_type` cash/credit overrides.

4. **Bulk Production Entry Panel**
   - Built a fast, grid-based bulk entry screen (`bulk_production_view.py`) to record multiple production batch runs at once.
   - Integrated a compound raw material sufficiency pre-check before saving to prevent batch ledger post failures.

5. **Local Tools, Online Backups, & Peachtree Exporter**
   - Developed a Peachtree / Sage 50 accounting exporter generating fully balanced journal CSVs (Sales, Receipts, Expenses, Inbound Purchases, and Waste) directly from GL journal entries.
   - Integrated a safe database online snapshot copier (`backup_service.py`) using sqlite3 online backup APIs to prevent file locking.
   - Enabled professional A5 sign-off PDF voucher re-printing for all transaction types (SV, CRV, EV, SRV, PRODUCTION, WV) from a native file browser.

6. **Finished Product Waste Ledger**
   - Built finished block waste registration dialogs (`waste_dialog.py`) connected to dynamic subledger stock deductions and double-entry postings (debiting `GL-5102 Factory Waste` and crediting `GL-1104 Finished Goods`).

## v3.0.0 — SuperERP Core Edition Upgrade

1. **Unified Database Migration & SQLAlchemy ORM**
   - Replaced raw SQLite queries with SQLAlchemy database models in `models.py`.
   - Enabled Write-Ahead Logging (WAL) and index structures on dates/codes for robust offline transactions.
   - Unified raw materials and finished products under a single `Article` schema tracking multi-location stock (Warehouse/Curing vs. Shop Floor).

2. **Double-Entry Transaction Posting Engine**
   - Created `ledger_service` to process transaction headers with sequential numbering (`[TYPE]-[YYYYMMDD]-[SEQ]`).
   - Posts balanced, immutable double-entry General Ledger rows (Debit & Credit balances) and physical stock movements (Inventory Ledger).
   - Supports transactional voids by automatically logging opposite compensating entries to preserve clear historical audit trails.

3. **The 8 Core Operational Vouchers**
   - **SRV** (Store Receipt Voucher): Materials purchase inbound.
   - **SIV** (Store Issue Voucher): Disposing aggregate/cement waste.
   - **SAV** (Stock Adjustment Voucher): Audits counted stock discrepancies.
   - **PRODUCTION**: Automatic formula/recipe consumption calculations logging manufacturing runs.
   - **FGTV** (Finished Goods Transfer): Curing yard to sales floor stock movements.
   - **CSV** & **CrSV**: Cash Sale and Credit Sale entries.
   - **CRV** (Cash Receipt Voucher): Customer collections on outstanding accounts receivable.

4. **Action-Level User Access Control (UAC) & Auto-Lockout**
   - Replaced generic role checking with granular action permissions nodes (e.g., `sale:void`, `inventory:adjust`).
   - Integrated **Supervisor Authorization Password Override Dialog**: Prompts for inline supervisor credentials when cashier/worker roles trigger unauthorized operations, avoiding sign-out loops.
   - Implemented an Inactivity Event Filter that automatically triggers the lock screen after 120 seconds of idle time.

5. **Sidebar UI Consolidation**
   - Restructured the sidebar navigation drawer into exactly 5 main panels: Dashboard, Logistics, Production, Sales, and User / Audits.

6. **Interactive Voucher Document Browser**
   - Added a full split-panel document browser sub-tab under User / Audits.
   - Filter and search all voucher headers with a paginated, search-attached table grid.
   - Selected voucher displays dual details pane: **Physical stock movements** (color-coded in green/red) and **Financial journal postings** with inline "Debits = Credits" reconciliation checks.
   - Perform secure supervisor-approved transactional voids directly from the detail pane.

7. **Virtual List Grid Pagination**
   - Developed `PaginatedTableWidget` querying SQLite `LIMIT` and `OFFSET` bounds dynamically, preventing UI thread freezing on large ledger tables.

8. **Premium QSS UI Refurbishment**
   - Refurbished Light and Dark stylesheet QSS definitions in `theme.py`.
   - Replaced default desktop scrollbars with custom, modern thin scrollbar handles.
   - Added subtle focus border highlight overlays for line text, double spin, and date pickers.
   - Implemented flat modern action buttons and alternating list line item backgrounds.

9. **Analytics Reports Overhaul & Fixes**
   - Re-routed all backend SQL query helpers to target the new vouchers and ledger tables.
   - Restructured reports no-data hint logic to safely check unified voucher date boundaries rather than legacy tables.

## v2 — Major update

1. **MN Construction rebrand**
   - Window title, sidebar, login screen, README, and PDF report header all rebranded.
   - PDF export filename now starts with `MN_Construction_report_`.

2. **New product category: PIPE (ቱቦ)**
   - Added 6 pipe products: ቱቦ ባለ 30, 40, 50, 60, 100, ቢረት 100.
   - Existing databases are auto-migrated to allow the new category.
   - Pipes use only Cement and TeTer00. TUBO_40's teter00=52.38288 is flagged for verification — edit in Products > Formula if wrong.

3. **New HCB product: HCBገተር** (cement 2.778, pumice 0.384)

4. **Fixed HCB N-variant formulas**
   - HCB10N, HCB15N, HCB20N now use only Cement + Pumice. TeTer00 and TeTer01 are set to 0.
   - Old production records retain their original formula (versioned by effective_from) so historical reports stay accurate.

5. **"Made by" worker tracking**
   - New `made_by` field on production: which worker physically made the blocks.
   - Autocomplete from the last 10 distinct names.
   - Appears in production history and in all reports.

6. **Reports overhaul**
   - Production and Sales tabs split into 3 sub-tables: HCB, Terazo, Pipes (ቱቦ).
     Pieces and m² are never mixed.
   - Production columns: Date / Code / Product / Quantity / Unit / Made By / Runs / Notes
   - Sales columns:      Date / Code / Product / Customer / Quantity / Unit / Unit Price / Total / Notes
   - Material Usage now shows: Code / Material / Opening Stock / Total Used / Purchased / Remaining / Unit
   - New **Finished Goods** sub-tab: per product — produced in period, sold in period, current stock.
   - **Customer filter** dropdown for Sales tab — answers "how much did we sell to Mr X between A and B".
   - **All Time** period option added.
   - Free editing of From/To date pickers — period auto-switches to "Custom".
   - PDF export matches the new structure with per-category sections.
   - PDF includes Amharic font auto-detection (Nyala/Ebrima/AbyssinicaSIL/NotoSansEthiopic) with safe fallback to product codes.

7. **Global search bar**
   - Sales, Production, Inventory Stock History, Products, and all Reports tabs now have a search box.
   - Case-insensitive substring search across all visible columns.

8. **Dashboard popovers**
   - Click any of the four stat cards (Revenue Today / Sales Today / Production Today / Low Stock Alerts) to open a detail popup with today's underlying records.

## v1 — Initial release

- HCB and Terazo factory management
- Offline SQLite database
- Inventory, Production, Sales, Reports, Products, Users
- Light + dark theme
- PDF export
