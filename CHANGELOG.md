# Changelog

## v4.1 — Polish pass (every screen audited and fixed)

**Bug fixes**
- Login: cursor now auto-focuses on the username field; on failed login, password clears and refocuses
- Inventory: "Add Stock" button is disabled until quantity > 0 (no more bouncing back with an error); "Adjust Stock" dialog now shows the live change preview (+ or −); stock-history "Type" column shows friendly labels instead of raw 'purchase'/'production'/'adjustment'
- Production: "Confirm Production" button is automatically disabled when any material is short — no more attempting impossible runs; success message now shows the new voucher number (PV-####); edit/delete dialogs no longer crash when a record was already deleted by another action
- Sales: removed annoying "no customer name" warning (anonymous cash sales are fine now); success message shows the voucher number; "Amount paid (leave 0 = full cash)" label is clearer; the same edit/delete crash guard as production
- Customers: payment dialog has autocomplete from existing customer names; statement dialog shows a friendly empty state when no records; new "Record Payment" success shows the receipt voucher number; empty customer list shows a hint instead of being blank
- Expenses: success shows the EV voucher number; empty list shows a hint; cleaned up the summary line (no more trailing pipe with nothing after it)
- Bulk Entry: product list now refreshes when the tab is opened (so admin changes elsewhere are visible); failed rows are kept (with friendly error list) so you can fix and resubmit instead of losing your work
- Audit Log: every action is now a human-friendly label ("Production recorded" instead of `production_create`); failed logins and deletes show in red
- Users: password fields now require confirmation (typed twice to catch typos); minimum 4 characters enforced; duplicate username produces a clear error message; tab auto-refreshes when opened
- Tools / Restore: app now properly closes after a restore (was previously running with stale data in memory — risky); date validation on accounting export
- Reports: "This Week" now means Monday-of-this-week through today; "This Month" means the 1st of the current month through today (previously both used "last N days" which was misleading); reversed date ranges auto-swap and tell you in the status bar; PDF export shows a friendly "file is open elsewhere" error instead of a Python traceback

**Validation improvements**
- Negative product sell prices now rejected (was silently accepted before)
- Empty product names now rejected
- Negative low-stock thresholds now rejected
- All PDF export paths now handle PermissionError with a friendly "close the file and try again" message instead of crashing

**Theme polish**
- Every label across the app now uses semantic style classes ("pagetitle", "sectionhead", "subhead", "hint", "emptystate", "summarybox") instead of hardcoded colors
- Switching dark mode now actually re-themes every screen properly — previously many headers stayed dark blue on dark blue and were unreadable
- Login window itself now follows the theme

## v4 — Vouchers, expanded audit, Peachtree export
*(prior release)*

## v3 — 12 desktop features
*(prior release)*

## v2 — Major update
*(prior release)*

## v1 — Initial release
*(prior release)*
