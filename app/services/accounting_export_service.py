"""
Accounting export — generates CSV files an accountant can import into
Peachtree / Sage 50 (or any other double-entry system).
Queries our unified double-entry Vouchers and Journal Entries.
"""
import csv
from pathlib import Path
from app.database.db import get_connection

def _export_voucher_types(v_types: list, filename: str, date_from: str, date_to: str, out_dir: str) -> str:
    path = Path(out_dir) / filename
    conn = get_connection()
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Date", "Voucher No", "Account", "Debit", "Credit", "Description", "Reference"])
            
            placeholders = ",".join(["?"] * len(v_types))
            sql = f"""
                SELECT date(v.created_at) AS dt, v.voucher_no, v.customer_name, v.note, v.made_by,
                       je.account_code, je.debit, je.credit
                FROM vouchers v
                JOIN journal_entries je ON je.voucher_id = v.id
                WHERE v.voucher_type IN ({placeholders})
                  AND date(v.created_at) BETWEEN ? AND ?
                  AND v.state = 'POSTED'
                ORDER BY v.created_at, v.id, je.id
            """
            params = list(v_types) + [date_from, date_to]
            rows = conn.execute(sql, params).fetchall()
            
            for r in rows:
                desc = r["note"] or f"{r['account_code']} entry"
                ref = r["customer_name"] or r["made_by"] or ""
                w.writerow([
                    r["dt"],
                    r["voucher_no"],
                    r["account_code"],
                    f"{r['debit']:.2f}" if r["debit"] else "",
                    f"{r['credit']:.2f}" if r["credit"] else "",
                    desc,
                    ref
                ])
        return str(path)
    finally:
        conn.close()

def export_period(date_from: str, date_to: str, out_dir: str):
    """Write 5 CSVs into out_dir for the given period. Returns list of file paths."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    files = []
    
    # 1. Sales journal: CASH_SALE, CREDIT_SALE
    files.append(_export_voucher_types(
        ["CASH_SALE", "CREDIT_SALE"], 
        f"sales_journal_{date_from}_to_{date_to}.csv", 
        date_from, date_to, out_dir
    ))
    
    # 2. Receipts journal (CRV)
    files.append(_export_voucher_types(
        ["CRV"], 
        f"receipts_journal_{date_from}_to_{date_to}.csv", 
        date_from, date_to, out_dir
    ))
    
    # 3. Expense journal (EV)
    files.append(_export_voucher_types(
        ["EV"], 
        f"expenses_journal_{date_from}_to_{date_to}.csv", 
        date_from, date_to, out_dir
    ))
    
    # 4. Material purchases journal (SRV)
    files.append(_export_voucher_types(
        ["SRV"], 
        f"purchases_journal_{date_from}_to_{date_to}.csv", 
        date_from, date_to, out_dir
    ))
    
    # 5. Waste journal (WV)
    files.append(_export_voucher_types(
        ["WV"], 
        f"waste_journal_{date_from}_to_{date_to}.csv", 
        date_from, date_to, out_dir
    ))
    
    return files
