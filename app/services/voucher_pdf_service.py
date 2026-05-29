"""
Voucher PDF generator. Produces clean A5 voucher prints for any transaction type:
  SV - Sales Voucher    RV - Receipt Voucher    EV - Expense Voucher
  PV - Production Voucher  MV - Material Voucher  WV - Waste Voucher

Designed for printing and physical sign-off.
Queries our unified double-entry Voucher, JournalEntry, and subledger tables dynamically.
"""
import re
from pathlib import Path
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Table, TableStyle)

from app.database.db import get_connection
from app.services.report_service import _register_amharic_font, _amharic_safe


def _fetch_voucher(voucher_no: str):
    """Find any voucher by its number across the unified double-entry tables.
    Returns (kind, row_dict, related_dict)."""
    conn = get_connection()
    try:
        # Get voucher header
        v = conn.execute("SELECT * FROM vouchers WHERE voucher_no = ?", (voucher_no,)).fetchone()
        if not v:
            return (None, None, None)
        v = dict(v)
        
        # Get username of creator
        u = conn.execute("SELECT username FROM users WHERE id = ?", (v["created_by_id"],)).fetchone()
        v["recorded_by"] = u["username"] if u else "(system)"
        
        v_type = v["voucher_type"]
        if v_type in ("CASH_SALE", "CREDIT_SALE"):
            # Sales Voucher
            # Total credit to GL-4101 Sales Revenue
            total_r = conn.execute(
                "SELECT credit FROM journal_entries WHERE voucher_id = ? AND account_code = 'GL-4101 Sales Revenue'",
                (v["id"],)
            ).fetchone()
            total = total_r["credit"] if total_r else 0.0
            
            # Paid Debit to GL-1101 Cash on Hand
            paid_r = conn.execute(
                "SELECT debit FROM journal_entries WHERE voucher_id = ? AND account_code = 'GL-1101 Cash on Hand'",
                (v["id"],)
            ).fetchone()
            paid = paid_r["debit"] if paid_r else 0.0
            
            # Product details
            prod_r = conn.execute(
                """SELECT ABS(il.qty_change) AS quantity, il.cost_rate,
                          a.code AS product_code, a.name AS product_name, a.unit AS input_unit
                   FROM inventory_ledger il
                   JOIN articles a ON a.id = il.article_id
                   WHERE il.voucher_id = ? AND il.qty_change < 0""",
                (v["id"],)
            ).fetchone()
            
            if prod_r:
                p = dict(prod_r)
                v.update({
                    "product_code": p["product_code"],
                    "product_name": p["product_name"],
                    "input_unit": p["input_unit"],
                    "quantity": p["quantity"],
                    "unit_price": round(total / p["quantity"], 2) if p["quantity"] else 0.0,
                    "total": total,
                    "amount_paid": paid
                })
            return ("Sales Voucher", v, None)
            
        elif v_type == "CRV":
            # Receipt Voucher
            # Amount credit to GL-1105 Accounts Receivable (or Debit to GL-1101)
            je = conn.execute(
                "SELECT debit FROM journal_entries WHERE voucher_id = ? AND account_code IN ('GL-1101 Cash on Hand', 'GL-1102 Bank')",
                (v["id"],)
            ).fetchone()
            amount = je["debit"] if je else 0.0
            
            # Fetch method from customer_payments if exists
            method_r = conn.execute(
                "SELECT method FROM customer_payments WHERE voucher_no = ?", (voucher_no,)
            ).fetchone()
            method = method_r["method"] if method_r else "cash"
            
            v.update({
                "amount": amount,
                "method": method
            })
            return ("Receipt Voucher", v, None)
            
        elif v_type == "EV":
            # Expense Voucher
            # Amount Debit to GL-5101 Operating Expenses
            je = conn.execute(
                "SELECT debit FROM journal_entries WHERE voucher_id = ? AND account_code = 'GL-5101 Operating Expenses'",
                (v["id"],)
            ).fetchone()
            amount = je["debit"] if je else 0.0
            
            # Category from expenses table
            cat_r = conn.execute(
                "SELECT category FROM expenses WHERE voucher_no = ?", (voucher_no,)
            ).fetchone()
            category = cat_r["category"] if cat_r else "Other"
            
            v.update({
                "amount": amount,
                "category": category,
                "description": v["note"]
            })
            return ("Expense Voucher", v, None)
            
        elif v_type == "SRV":
            # Material Purchase Voucher (SRV)
            # Material details (positive inventory movement qty_change > 0)
            mat_r = conn.execute(
                """SELECT il.qty_change AS qty, il.cost_rate AS unit_cost,
                          a.code AS material_code, a.name AS material_name, a.unit
                   FROM inventory_ledger il
                   JOIN articles a ON a.id = il.article_id
                   WHERE il.voucher_id = ? AND il.qty_change > 0""",
                (v["id"],)
            ).fetchone()
            
            if mat_r:
                m = dict(mat_r)
                v.update({
                    "material_code": m["material_code"],
                    "material_name": m["material_name"],
                    "unit": m["unit"],
                    "qty": m["qty"],
                    "unit_cost": m["unit_cost"],
                    "supplier_name": v["customer_name"] or "General Supplier"
                })
            return ("Material Purchase Voucher", v, None)
            
        elif v_type == "PRODUCTION":
            # Production Voucher
            # Product details (positive qty_change > 0)
            prod_r = conn.execute(
                """SELECT il.qty_change AS quantity,
                          a.code AS product_code, a.name AS product_name, a.unit AS input_unit
                   FROM inventory_ledger il
                   JOIN articles a ON a.id = il.article_id
                   WHERE il.voucher_id = ? AND il.qty_change > 0""",
                (v["id"],)
            ).fetchone()
            
            v.update({
                "cost_total": 0.0
            })
            
            if prod_r:
                p = dict(prod_r)
                v.update({
                    "product_code": p["product_code"],
                    "product_name": p["product_name"],
                    "input_unit": p["input_unit"],
                    "quantity": p["quantity"]
                })
            return ("Production Voucher", v, None)
            
        elif v_type == "WV":
            # Waste Voucher (WV)
            # Product details (negative qty_change < 0)
            prod_r = conn.execute(
                """SELECT ABS(il.qty_change) AS quantity,
                          a.code AS product_code, a.name AS product_name, a.unit AS input_unit
                   FROM inventory_ledger il
                   JOIN articles a ON a.id = il.article_id
                   WHERE il.voucher_id = ? AND il.qty_change < 0""",
                (v["id"],)
            ).fetchone()
            
            # Reason from waste table
            reason_r = conn.execute(
                "SELECT reason FROM waste WHERE voucher_no = ?", (voucher_no,)
            ).fetchone()
            reason = reason_r["reason"] if reason_r else "damaged"
            
            if prod_r:
                p = dict(prod_r)
                v.update({
                    "product_code": p["product_code"],
                    "product_name": p["product_name"],
                    "input_unit": p["input_unit"],
                    "quantity": p["quantity"],
                    "reason": reason
                })
            return ("Waste Voucher", v, None)
            
    finally:
        conn.close()
    return (None, None, None)


def export_voucher(voucher_no: str, out_path: str):
    """Render any voucher by its number to a PDF."""
    kind, row, _ = _fetch_voucher(voucher_no)
    if row is None:
        raise ValueError(f"Voucher {voucher_no} not found")

    font = _register_amharic_font()
    base = font[0] if font else "Helvetica"
    bold = font[1] if font else "Helvetica-Bold"

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(out_path, pagesize=A5,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet()
    title  = ParagraphStyle("t", parent=styles["Heading1"], fontSize=15,
                            textColor=colors.HexColor("#1F4E79"),
                            fontName=bold, alignment=1, spaceAfter=2)
    sub    = ParagraphStyle("s", parent=styles["Normal"], fontSize=10,
                            textColor=colors.grey, alignment=1, fontName=base,
                            spaceAfter=8)
    body   = ParagraphStyle("b", parent=styles["Normal"], fontSize=10,
                            fontName=base, spaceAfter=2)
    big    = ParagraphStyle("big", parent=styles["Normal"], fontSize=14,
                            fontName=bold, alignment=2)

    story = []
    story.append(Paragraph("MN Construction", title))
    story.append(Paragraph(kind, sub))

    # Header table: voucher number + date
    header_data = [
        [Paragraph(f"<b>Voucher No:</b>", body),
         Paragraph(voucher_no, body),
         Paragraph(f"<b>Date:</b>", body),
         Paragraph(_voucher_date(row, kind), body)]
    ]
    ht = Table(header_data, colWidths=[80, 100, 50, 80])
    ht.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BOX",    (0,0), (-1,-1), 0.5, colors.HexColor("#1F4E79")),
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#E8EEF7")),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING",(0,0), (-1,-1), 6),
        ("TOPPADDING",  (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
    ]))
    story.append(ht)
    story.append(Spacer(1, 12))

    # Body block per type
    if kind == "Sales Voucher":
        story.extend(_sales_body(row, body, big, base, bold))
    elif kind == "Receipt Voucher":
        story.extend(_receipt_body(row, body, big, base, bold))
    elif kind == "Expense Voucher":
        story.extend(_expense_body(row, body, big, base, bold))
    elif kind == "Material Purchase Voucher":
        story.extend(_material_body(row, body, big, base, bold))
    elif kind == "Production Voucher":
        story.extend(_production_body(row, body, big, base, bold))
    elif kind == "Waste Voucher":
        story.extend(_waste_body(row, body, big, base, bold))

    story.append(Spacer(1, 24))

    # Signature lines
    sig_data = [
        [Paragraph("<b>Prepared by:</b>", body),
         Paragraph(row.get("recorded_by") or "____________", body),
         Paragraph("<b>Approved by:</b>", body),
         Paragraph("____________", body)],
    ]
    sigt = Table(sig_data, colWidths=[70, 100, 70, 80])
    sigt.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "BOTTOM"),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("LINEBELOW", (1,0), (1,0), 0.5, colors.grey),
        ("LINEBELOW", (3,0), (3,0), 0.5, colors.grey),
    ]))
    story.append(sigt)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"<i>Issued {datetime.now():%Y-%m-%d %H:%M}</i>",
        ParagraphStyle("foot", parent=styles["Normal"], fontSize=8,
                       fontName=base, alignment=1, textColor=colors.grey)
    ))

    doc.build(story)
    return out_path


def _voucher_date(row, kind):
    return (row.get("sale_date") or row.get("payment_date") or
            row.get("expense_date") or row.get("production_date") or
            row.get("waste_date") or (row.get("created_at") or "")[:10] or "")


def _sales_body(s, body, big, base, bold):
    out = []
    out.append(Paragraph(f"<b>Customer:</b> {s.get('customer_name') or '—'}", body))
    out.append(Spacer(1, 6))
    unit = "pieces" if s["input_unit"] == "piece" else "m²"
    product = _amharic_safe(f"{s['product_code']} — {s['product_name']}", s['product_code'])
    line_data = [
        ["Item", "Qty", "Unit", "Unit Price", "Total"],
        [product, f"{s['quantity']:.2f}", unit,
         f"{s['unit_price']:,.2f}", f"{s['total']:,.2f}"],
    ]
    t = _line_table(line_data, base, bold)
    out.append(t); out.append(Spacer(1, 10))
    paid = s.get("amount_paid") or s["total"]
    bal = s["total"] - paid
    out.append(Paragraph(f"Total: {s['total']:,.2f} ETB", big))
    out.append(Paragraph(f"Paid:  {paid:,.2f} ETB", big))
    if bal > 0.001:
        out.append(Paragraph(
            f'<font color="#C0392B">Balance due: {bal:,.2f} ETB</font>', big))
    else:
        out.append(Paragraph('<font color="#27AE60">Paid in full</font>', big))
    if s.get("note"):
        out.append(Spacer(1, 6))
        out.append(Paragraph(f"<i>Note: {s['note']}</i>", body))
    return out


def _receipt_body(p, body, big, base, bold):
    out = []
    out.append(Paragraph(f"<b>Received from:</b> {p['customer_name']}", body))
    out.append(Paragraph(f"<b>Method:</b> {p.get('method') or '—'}", body))
    if p.get("note"):
        out.append(Paragraph(f"<b>Note:</b> {p['note']}", body))
    out.append(Spacer(1, 10))
    out.append(Paragraph(f"Amount received: {p['amount']:,.2f} ETB", big))
    return out


def _expense_body(e, body, big, base, bold):
    out = []
    out.append(Paragraph(f"<b>Category:</b> {e['category']}", body))
    out.append(Paragraph(f"<b>Description:</b> {e.get('description') or '—'}", body))
    out.append(Spacer(1, 10))
    out.append(Paragraph(f"Amount paid: {e['amount']:,.2f} ETB", big))
    return out


def _material_body(m, body, big, base, bold):
    out = []
    out.append(Paragraph(f"<b>Supplier:</b> {m.get('supplier_name') or '—'}", body))
    qty = m["qty"]; uc = m.get("unit_cost") or 0
    total = abs(qty) * uc
    line_data = [
        ["Material", "Qty", "Unit", "Unit Cost", "Total"],
        [f"{m['material_code']} — {m['material_name']}",
         f"{abs(qty):.3f}", m["unit"],
         f"{uc:,.2f}", f"{total:,.2f}"],
    ]
    out.append(_line_table(line_data, base, bold)); out.append(Spacer(1, 8))
    if total > 0:
        out.append(Paragraph(f"Total cost: {total:,.2f} ETB", big))
    if m.get("note"):
        out.append(Spacer(1, 4))
        out.append(Paragraph(f"<i>Note: {m['note']}</i>", body))
    return out


def _production_body(p, body, big, base, bold):
    out = []
    unit = "pieces" if p["input_unit"] == "piece" else "m²"
    product = _amharic_safe(f"{p['product_code']} — {p['product_name']}", p['product_code'])
    out.append(Paragraph(f"<b>Product:</b> {product}", body))
    out.append(Paragraph(f"<b>Quantity produced:</b> {p['quantity']:.2f} {unit}", body))
    out.append(Paragraph(f"<b>Made by:</b> {p.get('made_by') or '—'}", body))
    if p.get("cost_total"):
        out.append(Paragraph(f"<b>Material cost:</b> {p['cost_total']:,.2f} ETB", body))
    if p.get("note"):
        out.append(Paragraph(f"<i>Note: {p['note']}</i>", body))
    return out


def _waste_body(w, body, big, base, bold):
    out = []
    unit = "pieces" if w["input_unit"] == "piece" else "m²"
    product = _amharic_safe(f"{w['product_code']} — {w['product_name']}", w['product_code'])
    out.append(Paragraph(f"<b>Product:</b> {product}", body))
    out.append(Paragraph(f"<b>Quantity damaged:</b> {w['quantity']:.2f} {unit}", body))
    out.append(Paragraph(f"<b>Reason:</b> {w.get('reason') or '—'}", body))
    if w.get("note"):
        out.append(Paragraph(f"<i>Note: {w['note']}</i>", body))
    return out


def _line_table(data, base, bold):
    t = Table(data, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), bold),
        ("FONTNAME",   (0,1), (-1,-1), base),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("GRID",       (0,0), (-1,-1), 0.25, colors.grey),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
    ]))
    return t
