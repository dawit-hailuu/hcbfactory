"""
Accounting export — generates CSV files an accountant can import into
Peachtree / Sage 50 (or any other double-entry system).

We produce 5 files, all in standard CSV with these columns:
  Date, Voucher No, Account, Debit, Credit, Description, Reference

The mapping uses a simple Ethiopian small-business chart of accounts. The
accountant can rename accounts during Peachtree import — what matters is the
data is clean, complete, and reconcilable to voucher numbers.

Default account codes (editable by the accountant in Peachtree):
  1101  Cash on Hand            (asset)
  1102  Bank                    (asset)
  1201  Accounts Receivable     (asset)
  1301  Raw Materials Inventory (asset)
  1302  Finished Goods Inventory (asset)
  2101  Accounts Payable        (liability)
  4101  Sales Revenue           (income)
  5101  Cost of Goods Sold      (expense)
  6101  Salaries & Labor        (expense)
  6102  Utilities               (expense)
  6103  Rent                    (expense)
  6104  Transport               (expense)
  6105  Maintenance             (expense)
  6106  Materials Purchases     (expense)
  6107  Other Operating Expense (expense)
  6201  Waste / Loss            (expense)
"""
import csv
from pathlib import Path
from app.database.db import get_connection


ACCOUNTS = {
    "cash":          ("1101", "Cash on Hand"),
    "bank":          ("1102", "Bank"),
    "ar":            ("1201", "Accounts Receivable"),
    "raw_inventory": ("1301", "Raw Materials Inventory"),
    "fg_inventory":  ("1302", "Finished Goods Inventory"),
    "ap":            ("2101", "Accounts Payable"),
    "sales_revenue": ("4101", "Sales Revenue"),
    "cogs":          ("5101", "Cost of Goods Sold"),
    "Labor":         ("6101", "Salaries & Labor"),
    "Utilities":     ("6102", "Utilities"),
    "Rent":          ("6103", "Rent"),
    "Transport":     ("6104", "Transport"),
    "Maintenance":   ("6105", "Maintenance"),
    "Materials":     ("6106", "Materials Purchases"),
    "Other":         ("6107", "Other Operating Expense"),
    "waste":         ("6201", "Waste / Loss"),
}


def _row(date, voucher, key, debit=0, credit=0, desc="", ref=""):
    acc, name = ACCOUNTS.get(key, ("9999", str(key)))
    return [date, voucher or "", f"{acc} - {name}",
            f"{debit:.2f}" if debit else "",
            f"{credit:.2f}" if credit else "",
            desc, ref]


def export_period(date_from: str, date_to: str, out_dir: str):
    """Write 5 CSVs into out_dir for the given period. Returns list of file paths."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        files = []

        # --- Sales journal -----------------------------------------------------
        path = Path(out_dir) / f"sales_journal_{date_from}_to_{date_to}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Date","Voucher","Account","Debit","Credit","Description","Reference"])
            rows = conn.execute(
                """SELECT sale_date, voucher_no, customer_name, total,
                          COALESCE(amount_paid, total) AS paid,
                          COALESCE(cost_total, 0) AS cost
                     FROM sales
                    WHERE sale_date BETWEEN ? AND ?
                      AND deleted_at IS NULL
                    ORDER BY sale_date, id""",
                (date_from, date_to),
            ).fetchall()
            for s in rows:
                desc = f"Sale to {s['customer_name'] or '-'}"
                ref = s["voucher_no"] or ""
                # 1) Cash/AR (debit) vs Sales Revenue (credit)
                paid = s["paid"] or 0
                billed = s["total"] or 0
                if paid > 0:
                    w.writerow(_row(s["sale_date"], ref, "cash", debit=paid, desc=desc, ref=ref))
                ar = billed - paid
                if ar > 0:
                    w.writerow(_row(s["sale_date"], ref, "ar", debit=ar, desc=desc, ref=ref))
                w.writerow(_row(s["sale_date"], ref, "sales_revenue", credit=billed, desc=desc, ref=ref))
                # 2) COGS (debit) vs Finished Goods Inventory (credit) — if cost known
                cost = s["cost"] or 0
                if cost > 0:
                    w.writerow(_row(s["sale_date"], ref, "cogs", debit=cost, desc=f"COGS — {desc}", ref=ref))
                    w.writerow(_row(s["sale_date"], ref, "fg_inventory", credit=cost, desc=f"COGS — {desc}", ref=ref))
        files.append(str(path))

        # --- Receipts (customer payments) journal -----------------------------
        path = Path(out_dir) / f"receipts_journal_{date_from}_to_{date_to}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Date","Voucher","Account","Debit","Credit","Description","Reference"])
            rows = conn.execute(
                """SELECT payment_date, voucher_no, customer_name, amount,
                          COALESCE(method,'') AS method
                     FROM customer_payments
                    WHERE payment_date BETWEEN ? AND ?
                    ORDER BY payment_date, id""",
                (date_from, date_to),
            ).fetchall()
            for p in rows:
                ref = p["voucher_no"] or ""
                desc = f"Payment from {p['customer_name']} ({p['method'] or 'cash'})"
                # Cash/Bank debit, AR credit
                acct = "bank" if "bank" in (p["method"] or "").lower() else "cash"
                w.writerow(_row(p["payment_date"], ref, acct, debit=p["amount"], desc=desc, ref=ref))
                w.writerow(_row(p["payment_date"], ref, "ar", credit=p["amount"], desc=desc, ref=ref))
        files.append(str(path))

        # --- Expense journal ---------------------------------------------------
        path = Path(out_dir) / f"expenses_journal_{date_from}_to_{date_to}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Date","Voucher","Account","Debit","Credit","Description","Reference"])
            rows = conn.execute(
                """SELECT expense_date, voucher_no, category, amount,
                          COALESCE(description,'') AS description
                     FROM expenses
                    WHERE expense_date BETWEEN ? AND ?
                    ORDER BY expense_date, id""",
                (date_from, date_to),
            ).fetchall()
            for e in rows:
                ref = e["voucher_no"] or ""
                desc = f"{e['category']}: {e['description']}"
                w.writerow(_row(e["expense_date"], ref, e["category"], debit=e["amount"], desc=desc, ref=ref))
                w.writerow(_row(e["expense_date"], ref, "cash", credit=e["amount"], desc=desc, ref=ref))
        files.append(str(path))

        # --- Material purchases journal ---------------------------------------
        path = Path(out_dir) / f"purchases_journal_{date_from}_to_{date_to}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Date","Voucher","Account","Debit","Credit","Description","Reference"])
            rows = conn.execute(
                """SELECT sm.created_at AS dt, sm.voucher_no, sm.qty, sm.unit_cost,
                          sm.supplier_name, m.code AS material_code, m.name AS material_name
                     FROM stock_movements sm
                     JOIN materials m ON m.id = sm.material_id
                    WHERE sm.movement = 'purchase'
                      AND date(sm.created_at) BETWEEN ? AND ?
                    ORDER BY sm.created_at""",
                (date_from, date_to),
            ).fetchall()
            for s in rows:
                date = (s["dt"] or "")[:10]
                ref = s["voucher_no"] or ""
                uc = s["unit_cost"] or 0
                total = (s["qty"] or 0) * uc
                desc = f"Purchase {s['material_code']} from {s['supplier_name'] or '-'}"
                if total > 0:
                    w.writerow(_row(date, ref, "raw_inventory", debit=total, desc=desc, ref=ref))
                    w.writerow(_row(date, ref, "cash", credit=total, desc=desc, ref=ref))
        files.append(str(path))

        # --- Waste journal -----------------------------------------------------
        path = Path(out_dir) / f"waste_journal_{date_from}_to_{date_to}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Date","Voucher","Account","Debit","Credit","Description","Reference"])
            # waste cost = avg unit cost * qty
            rows = conn.execute(
                """SELECT w.waste_date, w.voucher_no, w.quantity, w.reason,
                          pr.code, pr.name,
                          COALESCE(
                            (SELECT SUM(p.cost_total)/NULLIF(SUM(p.quantity),0)
                               FROM production p
                              WHERE p.product_id = w.product_id
                                AND p.deleted_at IS NULL), 0) AS unit_cost
                     FROM waste w
                     JOIN products pr ON pr.id = w.product_id
                    WHERE w.waste_date BETWEEN ? AND ?
                    ORDER BY w.waste_date, w.id""",
                (date_from, date_to),
            ).fetchall()
            for r in rows:
                ref = r["voucher_no"] or ""
                uc = r["unit_cost"] or 0
                total = (r["quantity"] or 0) * uc
                desc = f"Waste {r['code']} ({r['reason'] or 'damaged'})"
                if total > 0:
                    w.writerow(_row(r["waste_date"], ref, "waste", debit=total, desc=desc, ref=ref))
                    w.writerow(_row(r["waste_date"], ref, "fg_inventory", credit=total, desc=desc, ref=ref))
        files.append(str(path))

        return files
    finally:
        conn.close()
