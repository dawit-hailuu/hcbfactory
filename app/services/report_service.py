"""
Reports service.
Aggregations for dashboard, PDF export (reportlab), and tabular reports
powered by the double-entry transaction ledgers.
"""
from datetime import datetime, timedelta
from pathlib import Path
from app.database.db import get_connection


def todays_sales():
    """Detailed list of all of today's sales for the dashboard popup."""
    conn = get_connection()
    try:
        today = conn.execute("SELECT date('now','localtime') AS d").fetchone()["d"]
        sql = """
            SELECT date(v.created_at) AS sale_date, v.customer_name, 
                   ABS(il.qty_change) AS quantity, (je.debit / ABS(il.qty_change)) AS unit_price,
                   je.debit AS total, a.code, a.name, a.unit AS input_unit
            FROM vouchers v
            JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change < 0
            JOIN articles a ON a.id = il.article_id
            JOIN journal_entries je ON je.voucher_id = v.id AND je.debit > 0
            WHERE v.voucher_type IN ('CASH_SALE', 'CREDIT_SALE')
              AND v.state = 'POSTED'
              AND date(v.created_at) = ?
            ORDER BY v.id DESC
        """
        rows = conn.execute(sql, (today,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def todays_production():
    """Detailed list of today's production runs for the dashboard popup."""
    conn = get_connection()
    try:
        today = conn.execute("SELECT date('now','localtime') AS d").fetchone()["d"]
        sql = """
            SELECT date(v.created_at) AS production_date, il.qty_change AS quantity,
                   v.made_by, v.note, a.code, a.name, a.unit AS input_unit
            FROM vouchers v
            JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change > 0
            JOIN articles a ON a.id = il.article_id
            WHERE v.voucher_type = 'PRODUCTION'
              AND v.state = 'POSTED'
              AND date(v.created_at) = ?
            ORDER BY v.id DESC
        """
        rows = conn.execute(sql, (today,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def dashboard_summary():
    """Single-shot dashboard query: today's totals + low-stock list."""
    conn = get_connection()
    try:
        today = conn.execute("SELECT date('now','localtime') AS d").fetchone()["d"]

        # Today's sales totals
        sales_sql = """
            SELECT COALESCE(SUM(ABS(il.qty_change)), 0) AS qty, 
                   COALESCE(SUM(je.debit), 0) AS revenue
            FROM vouchers v
            JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change < 0
            JOIN journal_entries je ON je.voucher_id = v.id AND je.debit > 0
            WHERE v.voucher_type IN ('CASH_SALE', 'CREDIT_SALE')
              AND v.state = 'POSTED'
              AND date(v.created_at) = ?
        """
        sales_today = conn.execute(sales_sql, (today,)).fetchone()

        # Today's production totals
        prod_sql = """
            SELECT COALESCE(SUM(il.qty_change), 0) AS qty
            FROM vouchers v
            JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change > 0
            WHERE v.voucher_type = 'PRODUCTION'
              AND v.state = 'POSTED'
              AND date(v.created_at) = ?
        """
        prod_today = conn.execute(prod_sql, (today,)).fetchone()

        # Materials list (RAW Category)
        materials_sql = """
            SELECT id, code, name, unit, warehouse_qty AS current_stock, low_stock_alert, cost_price AS unit_cost
            FROM articles
            WHERE category = 'RAW' AND is_active = True
            ORDER BY name
        """
        materials = [dict(r) for r in conn.execute(materials_sql).fetchall()]
        low_stock = [m for m in materials if m["current_stock"] <= m["low_stock_alert"]]

        # Finished goods list
        finished_sql = """
            SELECT id, code, name, category, unit AS input_unit, shop_floor_qty AS stock, sell_price, low_stock_alert
            FROM articles
            WHERE category != 'RAW' AND shop_floor_qty > 0 AND is_active = True
            ORDER BY category, code
        """
        finished = [dict(r) for r in conn.execute(finished_sql).fetchall()]

        return {
            "date": today,
            "sales_today_qty": sales_today["qty"],
            "sales_today_revenue": sales_today["revenue"],
            "production_today_qty": prod_today["qty"],
            "materials": materials,
            "low_stock": low_stock,
            "finished_products": finished,
        }
    finally:
        conn.close()


def production_report(date_from: str, date_to: str, category: str = None):
    """Detailed production rows grouped by (date, product, made_by)."""
    conn = get_connection()
    try:
        where = [
            "v.voucher_type = 'PRODUCTION'",
            "v.state = 'POSTED'",
            "date(v.created_at) BETWEEN ? AND ?"
        ]
        params = [date_from, date_to]
        if category:
            where.append("a.category = ?")
            params.append(category)
            
        sql = f"""
            SELECT date(v.created_at) AS production_date,
                   a.code, a.name, a.unit AS input_unit, a.category,
                   COALESCE(v.made_by, '') AS made_by,
                   SUM(il.qty_change) AS total_qty,
                   COUNT(DISTINCT v.id) AS runs,
                   GROUP_CONCAT(NULLIF(v.note, ''), ' | ') AS notes
            FROM vouchers v
            JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change > 0
            JOIN articles a ON a.id = il.article_id
            WHERE {' AND '.join(where)}
            GROUP BY date(v.created_at), a.code, a.name, a.unit, a.category, v.made_by
            ORDER BY date(v.created_at) DESC, a.code
        """
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def material_usage_report(date_from: str, date_to: str):
    """
    Detailed material report with opening stock, used, purchased, and remaining.
    Opening stock is calculated by summing all history prior to the range start.
    """
    conn = get_connection()
    try:
        # Load all active raw materials
        materials = conn.execute(
            """SELECT id, code, name, unit, warehouse_qty AS current_stock 
               FROM articles WHERE category = 'RAW' AND is_active = True 
               ORDER BY name"""
        ).fetchall()

        out = []
        for m in materials:
            # 1. Opening Stock: Sum all posted qty changes before date_from
            op_sql = """
                SELECT COALESCE(SUM(il.qty_change), 0) AS opening
                FROM inventory_ledger il
                JOIN vouchers v ON v.id = il.voucher_id
                WHERE il.article_id = ?
                  AND il.location = 'WAREHOUSE'
                  AND v.state = 'POSTED'
                  AND date(v.created_at) < ?
            """
            opening_stock = conn.execute(op_sql, (m["id"], date_from)).fetchone()["opening"]

            # 2. Used in period (negative quantity changes during production runs)
            used_sql = """
                SELECT COALESCE(SUM(il.qty_change), 0) AS consumed
                FROM inventory_ledger il
                JOIN vouchers v ON v.id = il.voucher_id
                WHERE il.article_id = ?
                  AND il.location = 'WAREHOUSE'
                  AND v.voucher_type = 'PRODUCTION'
                  AND v.state = 'POSTED'
                  AND date(v.created_at) BETWEEN ? AND ?
            """
            total_used = abs(conn.execute(used_sql, (m["id"], date_from, date_to)).fetchone()["consumed"])

            # 3. Purchased in period (positive qty changes in SRV)
            pur_sql = """
                SELECT COALESCE(SUM(il.qty_change), 0) AS purchased
                FROM inventory_ledger il
                JOIN vouchers v ON v.id = il.voucher_id
                WHERE il.article_id = ?
                  AND il.location = 'WAREHOUSE'
                  AND v.voucher_type = 'SRV'
                  AND v.state = 'POSTED'
                  AND date(v.created_at) BETWEEN ? AND ?
            """
            purchased = conn.execute(pur_sql, (m["id"], date_from, date_to)).fetchone()["purchased"]

            # 4. Total net change in period (all movements, including adjustments)
            net_sql = """
                SELECT COALESCE(SUM(il.qty_change), 0) AS net
                FROM inventory_ledger il
                JOIN vouchers v ON v.id = il.voucher_id
                WHERE il.article_id = ?
                  AND il.location = 'WAREHOUSE'
                  AND v.state = 'POSTED'
                  AND date(v.created_at) BETWEEN ? AND ?
            """
            net_change = conn.execute(net_sql, (m["id"], date_from, date_to)).fetchone()["net"]
            remaining = opening_stock + net_change

            out.append({
                "code":          m["code"],
                "name":          m["name"],
                "unit":          m["unit"],
                "opening_stock": opening_stock,
                "total_used":    total_used,
                "purchased":     purchased,
                "remaining":     remaining,
            })
        return out
    finally:
        conn.close()


def sales_report(date_from: str, date_to: str, category: str = None,
                 customer: str = None):
    """Detailed sales rows in double-entry structure."""
    conn = get_connection()
    try:
        where = [
            "v.voucher_type IN ('CASH_SALE', 'CREDIT_SALE')",
            "v.state = 'POSTED'",
            "date(v.created_at) BETWEEN ? AND ?"
        ]
        params = [date_from, date_to]
        if category:
            where.append("a.category = ?")
            params.append(category)
        if customer:
            where.append("LOWER(COALESCE(v.customer_name,'')) = LOWER(?)")
            params.append(customer)
            
        sql = f"""
            SELECT v.id, date(v.created_at) AS sale_date, a.code, a.name, a.unit AS input_unit, a.category,
                   COALESCE(v.customer_name, '') AS customer_name,
                   ABS(il.qty_change) AS quantity, (je.debit / ABS(il.qty_change)) AS unit_price,
                   je.debit AS total, COALESCE(v.note, '') AS note
            FROM vouchers v
            JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change < 0
            JOIN articles a ON a.id = il.article_id
            JOIN journal_entries je ON je.voucher_id = v.id AND je.debit > 0
            WHERE {' AND '.join(where)}
            ORDER BY date(v.created_at) DESC, v.id DESC
        """
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def finished_goods_report(date_from: str, date_to: str):
    """Per-product report: produced in period, sold in period, current stock."""
    conn = get_connection()
    try:
        sql = """
            SELECT a.code, a.name, a.category, a.unit AS input_unit, 
                   (COALESCE(a.warehouse_qty, 0) + COALESCE(a.shop_floor_qty, 0)) AS current_stock,
                   COALESCE((
                       SELECT SUM(il.qty_change) 
                       FROM inventory_ledger il
                       JOIN vouchers v ON v.id = il.voucher_id
                       WHERE il.article_id = a.id
                         AND il.location = 'WAREHOUSE'
                         AND il.qty_change > 0
                         AND v.voucher_type = 'PRODUCTION'
                         AND v.state = 'POSTED'
                         AND date(v.created_at) BETWEEN ? AND ?
                   ), 0.0) AS produced,
                   COALESCE((
                       SELECT SUM(ABS(il.qty_change)) 
                       FROM inventory_ledger il
                       JOIN vouchers v ON v.id = il.voucher_id
                       WHERE il.article_id = a.id
                         AND il.location = 'SHOP_FLOOR'
                         AND il.qty_change < 0
                         AND v.voucher_type IN ('CASH_SALE', 'CREDIT_SALE')
                         AND v.state = 'POSTED'
                         AND date(v.created_at) BETWEEN ? AND ?
                   ), 0.0) AS sold
            FROM articles a
            WHERE a.category != 'RAW' AND a.is_active = True
            ORDER BY a.category, a.code
        """
        rows = conn.execute(sql, (date_from, date_to, date_from, date_to)).fetchall()

        return [dict(r) for r in rows]
    finally:
        conn.close()


def distinct_customers():
    """Sorted list of distinct customer names ever used in sales vouchers."""
    conn = get_connection()
    try:
        sql = """
            SELECT DISTINCT customer_name FROM vouchers
            WHERE customer_name IS NOT NULL 
              AND TRIM(customer_name) != '' 
              AND voucher_type IN ('CASH_SALE', 'CREDIT_SALE')
            ORDER BY LOWER(customer_name)
        """
        rows = conn.execute(sql).fetchall()
        return [r["customer_name"] for r in rows]
    finally:
        conn.close()


def date_range_for(period: str):
    today = datetime.now().date()
    if period == "today":
        return today.isoformat(), today.isoformat()
    if period == "week":
        start = today - timedelta(days=6)
        return start.isoformat(), today.isoformat()
    if period == "month":
        start = today - timedelta(days=29)
        return start.isoformat(), today.isoformat()
    if period == "year":
        start = today.replace(month=1, day=1)
        return start.isoformat(), today.isoformat()
    raise ValueError(f"unknown period {period}")


# PDF export — uses reportlab
_FONT_REGISTERED = None


def _register_amharic_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED is not None:
        return _FONT_REGISTERED

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    candidates = [
        ("AbyssinicaSIL", "C:\\Windows\\Fonts\\AbyssinicaSIL-R.ttf", None),
        ("Nyala",         "C:\\Windows\\Fonts\\nyala.ttf",            None),
        ("Ebrima",        "C:\\Windows\\Fonts\\ebrima.ttf",           "C:\\Windows\\Fonts\\ebrimabd.ttf"),
        ("NotoSansEthiopic", "/usr/share/fonts/truetype/noto/NotoSansEthiopic-Regular.ttf",
                             "/usr/share/fonts/truetype/noto/NotoSansEthiopic-Bold.ttf"),
        ("AbyssinicaSIL", "/usr/share/fonts/truetype/abyssinica/AbyssinicaSIL-R.ttf", None),
    ]
    for name, regular, bold in candidates:
        try:
            if regular and os.path.exists(regular):
                pdfmetrics.registerFont(TTFont(name, regular))
                bold_name = name + "-Bold"
                if bold and os.path.exists(bold):
                    pdfmetrics.registerFont(TTFont(bold_name, bold))
                else:
                    bold_name = name
                _FONT_REGISTERED = (name, bold_name)
                return _FONT_REGISTERED
        except Exception:
            continue

    _FONT_REGISTERED = False
    return False


def _amharic_safe(text: str, fallback: str) -> str:
    if _register_amharic_font():
        return text
    if any('\u1200' <= ch <= '\u137F' for ch in (text or "")):
        return fallback
    return text


def export_pdf(report_type: str, date_from: str, date_to: str, out_path: str,
               customer: str = None):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle)

    font = _register_amharic_font()
    base_font = font[0] if font else "Helvetica"
    bold_font = font[1] if font else "Helvetica-Bold"

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(out_path, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Heading1"],
                                 fontSize=18, textColor=colors.HexColor("#1F4E79"),
                                 spaceAfter=6, fontName=bold_font)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"],
                               fontSize=10, textColor=colors.grey, spaceAfter=12,
                               fontName=base_font)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                        fontSize=13, textColor=colors.HexColor("#1F4E79"),
                        spaceBefore=10, spaceAfter=6, fontName=bold_font)
    h3 = ParagraphStyle("h3", parent=styles["Heading3"],
                        fontSize=11, textColor=colors.HexColor("#2E86C1"),
                        spaceBefore=6, spaceAfter=4, fontName=bold_font)
    body = ParagraphStyle("body", parent=styles["Normal"],
                          fontSize=9, fontName=base_font)

    story = []
    story.append(Paragraph("MN Construction — Factory Report", title_style))
    sub_text = (f"Type: {report_type.title()} &nbsp;&nbsp; "
                f"Period: {date_from} to {date_to} &nbsp;&nbsp; "
                f"Generated: {datetime.now():%Y-%m-%d %H:%M}")
    if customer:
        sub_text += f" &nbsp;&nbsp; Customer: {customer}"
    story.append(Paragraph(sub_text, sub_style))

    def add_table(title, headers, data_rows, totals=None):
        story.append(Paragraph(title, h3))
        if not data_rows:
            story.append(Paragraph("<i>No records in this period.</i>", body))
            story.append(Spacer(1, 6))
            return
        table_data = [headers] + data_rows
        if totals:
            table_data.append(totals)
        t = Table(table_data, repeatRows=1, hAlign="LEFT")
        style = TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("FONTNAME",    (0,0), (-1,0), bold_font),
            ("FONTNAME",    (0,1), (-1,-1), base_font),
            ("FONTSIZE",    (0,0), (-1,-1), 8),
            ("GRID",        (0,0), (-1,-1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0,1), (-1,-1),
                [colors.whitesmoke, colors.white]),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
            ("RIGHTPADDING",(0,0), (-1,-1), 4),
        ])
        if totals:
            style.add("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#E8EEF7"))
            style.add("FONTNAME",   (0,-1), (-1,-1), bold_font)
        t.setStyle(style)
        story.append(t)
        story.append(Spacer(1, 6))

    # Production Grouped per Category
    if report_type in ("production", "combined"):
        story.append(Paragraph("Production", h2))
        for cat, label in (("HCB","HCB"), ("TERAZO","Terazo"), ("PIPE","Pipes (ቱቦ)")):
            rows = production_report(date_from, date_to, category=cat)
            data = [[
                r["production_date"], r["code"],
                _amharic_safe(r["name"], r["code"]),
                f"{r['total_qty']:.2f}",
                "pieces" if r["input_unit"]=="piece" else "m²",
                _amharic_safe(r["made_by"], r["made_by"]) if r["made_by"] else "",
                r["runs"],
                _amharic_safe(r["notes"] or "", "") if r["notes"] else "",
            ] for r in rows]
            total_qty = sum(r["total_qty"] for r in rows)
            unit_label = "pieces" if cat != "TERAZO" else "m²"
            totals = (["TOTAL","","",f"{total_qty:.2f}", unit_label,"", sum(r["runs"] for r in rows), ""]
                      if rows else None)
            add_table(f"{label}",
                      ["Date","Code","Product","Qty","Unit","Made By","Runs","Notes"],
                      data, totals=totals)

    # Material Usage
    if report_type in ("materials", "combined"):
        rows = material_usage_report(date_from, date_to)
        data = [[r["code"], r["name"],
                 f"{r['opening_stock']:.3f}",
                 f"{r['total_used']:.3f}",
                 f"{r['purchased']:.3f}",
                 f"{r['remaining']:.3f}",
                 r["unit"]] for r in rows]
        add_table("Material Usage",
                  ["Code","Material","Opening","Used","Purchased","Remaining","Unit"], data)

    # Sales Grouped per Category
    if report_type in ("sales", "combined"):
        story.append(Paragraph("Sales", h2))
        for cat, label in (("HCB","HCB"), ("TERAZO","Terazo"), ("PIPE","Pipes (ቱቦ)")):
            rows = sales_report(date_from, date_to, category=cat, customer=customer)
            data = [[
                r["sale_date"], r["code"],
                _amharic_safe(r["name"], r["code"]),
                r["customer_name"] or "",
                f"{r['quantity']:.2f}",
                "pieces" if r["input_unit"]=="piece" else "m²",
                f"{r['unit_price']:,.2f}",
                f"{r['total']:,.2f}",
                _amharic_safe(r["note"] or "", "") if r["note"] else "",
            ] for r in rows]
            total_qty = sum(r["quantity"] for r in rows)
            total_rev = sum(r["total"] for r in rows)
            unit_label = "pieces" if cat != "TERAZO" else "m²"
            totals = (["TOTAL","","","", f"{total_qty:.2f}", unit_label, "",
                       f"{total_rev:,.2f}", ""] if rows else None)
            add_table(f"{label}",
                      ["Date","Code","Product","Customer","Qty","Unit","Unit Price","Total (ETB)","Note"],
                      data, totals=totals)

    # Finished Goods stock
    if report_type in ("finished", "combined"):
        rows = finished_goods_report(date_from, date_to)
        story.append(Paragraph("Finished Goods", h2))
        for cat, label in (("HCB","HCB"), ("TERAZO","Terazo"), ("PIPE","Pipes (ቱቦ)")):
            sub = [r for r in rows if r["category"] == cat]
            data = [[
                r["code"], _amharic_safe(r["name"], r["code"]),
                f"{r['produced']:.2f}",
                f"{r['sold']:.2f}",
                f"{r['current_stock']:.2f}",
                "pieces" if r["input_unit"]=="piece" else "m²",
            ] for r in sub]
            add_table(f"{label}",
                      ["Code","Product","Produced","Sold","In Stock","Unit"], data)

    doc.build(story)
    return out_path


def worker_performance(date_from: str, date_to: str):
    """Per-worker production output over the period, broken by category."""
    conn = get_connection()
    try:
        sql = """
            SELECT COALESCE(NULLIF(TRIM(v.made_by),''),'(unknown)') AS made_by,
                   a.category, a.unit AS input_unit,
                   SUM(il.qty_change) AS total_qty,
                   COUNT(DISTINCT v.id) AS runs
            FROM vouchers v
            JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change > 0
            JOIN articles a ON a.id = il.article_id
            WHERE v.voucher_type = 'PRODUCTION'
              AND v.state = 'POSTED'
              AND date(v.created_at) BETWEEN ? AND ?
            GROUP BY made_by, a.category, a.unit
            ORDER BY made_by, a.category
        """
        rows = conn.execute(sql, (date_from, date_to)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
