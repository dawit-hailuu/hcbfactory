"""
Reports service.

Aggregations for dashboard + daily/weekly/monthly reports.
PDF export via reportlab.
"""
from datetime import datetime, timedelta
from pathlib import Path
from app.database.db import get_connection


def todays_sales():
    """Detailed list of all of today's sales for the dashboard popup."""
    conn = get_connection()
    try:
        today = conn.execute("SELECT date('now','localtime') AS d").fetchone()["d"]
        rows = conn.execute(
            """SELECT s.sale_date, s.customer_name, s.quantity, s.unit_price, s.total,
                      pr.code, pr.name, pr.input_unit
                 FROM sales s
                 JOIN products pr ON pr.id = s.product_id
                WHERE s.sale_date = ?
                ORDER BY s.id DESC""",
            (today,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def todays_production():
    """Detailed list of today's production runs for the dashboard popup."""
    conn = get_connection()
    try:
        today = conn.execute("SELECT date('now','localtime') AS d").fetchone()["d"]
        rows = conn.execute(
            """SELECT p.production_date, p.quantity, p.made_by, p.note,
                      pr.code, pr.name, pr.input_unit
                 FROM production p
                 JOIN products pr ON pr.id = p.product_id
                WHERE p.production_date = ?
                ORDER BY p.id DESC""",
            (today,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def dashboard_summary():
    """Single-shot dashboard query: today's totals + low-stock list."""
    conn = get_connection()
    try:
        today = conn.execute("SELECT date('now','localtime') AS d").fetchone()["d"]

        sales_today = conn.execute(
            """SELECT COALESCE(SUM(quantity),0) AS qty,
                      COALESCE(SUM(total),0)    AS revenue,
                      COALESCE(SUM(cost_total),0) AS cost
               FROM sales WHERE sale_date = ? AND deleted_at IS NULL""", (today,)
        ).fetchone()

        prod_today = conn.execute(
            """SELECT COALESCE(SUM(quantity),0) AS qty
               FROM production WHERE production_date = ? AND deleted_at IS NULL""", (today,)
        ).fetchone()

        materials = [dict(r) for r in conn.execute(
            "SELECT * FROM materials ORDER BY name"
        ).fetchall()]

        low_stock = [m for m in materials if m["current_stock"] <= m["low_stock_alert"]]

        finished = [dict(r) for r in conn.execute(
            "SELECT * FROM products WHERE stock > 0 ORDER BY category, code"
        ).fetchall()]

        return {
            "date": today,
            "sales_today_qty": sales_today["qty"],
            "sales_today_revenue": sales_today["revenue"],
            "sales_today_cost": sales_today["cost"],
            "sales_today_profit": sales_today["revenue"] - sales_today["cost"],
            "production_today_qty": prod_today["qty"],
            "materials": materials,
            "low_stock": low_stock,
            "finished_products": finished,
        }
    finally:
        conn.close()


def production_report(date_from: str, date_to: str, category: str = None):
    """Detailed production rows grouped by (date, product, made_by).
    Filter by category ('HCB'/'TERAZO'/'PIPE') if given.
    Returns one row per (date, product, made_by) combination — readable in a table.
    """
    conn = get_connection()
    try:
        where = ["p.production_date BETWEEN ? AND ?"]
        params = [date_from, date_to]
        if category:
            where.append("pr.category = ?")
            params.append(category)
        sql = f"""
            SELECT p.production_date,
                   pr.code, pr.name, pr.input_unit, pr.category,
                   COALESCE(p.made_by, '') AS made_by,
                   SUM(p.quantity) AS total_qty,
                   COUNT(*) AS runs,
                   GROUP_CONCAT(NULLIF(p.note, ''), ' | ') AS notes
            FROM production p
            JOIN products pr ON pr.id = p.product_id
            WHERE {' AND '.join(where)}
            GROUP BY p.production_date, pr.code, pr.name, pr.input_unit, pr.category, made_by
            ORDER BY p.production_date DESC, pr.code
        """
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def material_usage_report(date_from: str, date_to: str):
    """Detailed material report with opening stock, used, purchased, and remaining.

    For each material:
      - current_stock      = right now (from materials table)
      - total_used         = sum of |qty| from stock_movements where movement='production'
                             AND created_at falls within [date_from, date_to+1)
      - purchased          = sum of qty (positive) from stock_movements where
                             movement='purchase' AND created_at in range
      - opening_stock      = current_stock + total_used - purchased + adjustments_in_period
                             (i.e. work backwards from now)
    """
    conn = get_connection()
    try:
        # End of day = date_to + ' 23:59:59' for inclusive range
        rng_lo = f"{date_from} 00:00:00"
        rng_hi = f"{date_to} 23:59:59"

        rows = conn.execute(
            """SELECT id, code, name, unit, current_stock
                 FROM materials ORDER BY name"""
        ).fetchall()

        out = []
        for m in rows:
            used_row = conn.execute(
                """SELECT COALESCE(SUM(qty), 0) AS s
                   FROM stock_movements
                   WHERE material_id = ?
                     AND movement = 'production'
                     AND created_at BETWEEN ? AND ?""",
                (m["id"], rng_lo, rng_hi),
            ).fetchone()
            total_used = abs(used_row["s"])

            purchased_row = conn.execute(
                """SELECT COALESCE(SUM(qty), 0) AS s
                   FROM stock_movements
                   WHERE material_id = ?
                     AND movement = 'purchase'
                     AND created_at BETWEEN ? AND ?""",
                (m["id"], rng_lo, rng_hi),
            ).fetchone()
            purchased = purchased_row["s"]

            # Net change in period from ANY movement type (incl. adjustments)
            net_row = conn.execute(
                """SELECT COALESCE(SUM(qty), 0) AS s
                   FROM stock_movements
                   WHERE material_id = ?
                     AND created_at BETWEEN ? AND ?""",
                (m["id"], rng_lo, rng_hi),
            ).fetchone()
            net_change = net_row["s"]

            # Working backwards: opening = current - net_change_during_period
            opening_stock = m["current_stock"] - net_change

            out.append({
                "code":          m["code"],
                "name":          m["name"],
                "unit":          m["unit"],
                "opening_stock": opening_stock,
                "total_used":    total_used,
                "purchased":     purchased,
                "remaining":     m["current_stock"],
            })
        return out
    finally:
        conn.close()


def sales_report(date_from: str, date_to: str, category: str = None,
                 customer: str = None):
    """Detailed per-sale rows. Each sale is its own line so reports show
    date / customer / product / qty / unit price / total.
    """
    conn = get_connection()
    try:
        where = ["s.sale_date BETWEEN ? AND ?"]
        params = [date_from, date_to]
        if category:
            where.append("pr.category = ?")
            params.append(category)
        if customer:
            where.append("LOWER(COALESCE(s.customer_name,'')) = LOWER(?)")
            params.append(customer)
        sql = f"""
            SELECT s.id, s.sale_date, pr.code, pr.name, pr.input_unit, pr.category,
                   COALESCE(s.customer_name, '') AS customer_name,
                   s.quantity, s.unit_price, s.total,
                   COALESCE(s.note, '') AS note
            FROM sales s
            JOIN products pr ON pr.id = s.product_id
            WHERE {' AND '.join(where)}
            ORDER BY s.sale_date DESC, s.id DESC
        """
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def finished_goods_report(date_from: str, date_to: str):
    """Per-product report: produced in period, sold in period, current stock.
    Splits naturally by category, since each product carries its own category.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT pr.code, pr.name, pr.category, pr.input_unit, pr.stock AS current_stock,
                   COALESCE((SELECT SUM(p.quantity) FROM production p
                              WHERE p.product_id = pr.id
                                AND p.production_date BETWEEN ? AND ?), 0) AS produced,
                   COALESCE((SELECT SUM(s.quantity) FROM sales s
                              WHERE s.product_id = pr.id
                                AND s.sale_date BETWEEN ? AND ?), 0) AS sold
            FROM products pr
            ORDER BY pr.category, pr.code
            """,
            (date_from, date_to, date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def distinct_customers():
    """Return a sorted list of distinct customer names ever used (case-preserving)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT DISTINCT customer_name FROM sales
               WHERE customer_name IS NOT NULL AND TRIM(customer_name) != ''
               ORDER BY LOWER(customer_name)"""
        ).fetchall()
        return [r["customer_name"] for r in rows]
    finally:
        conn.close()


def date_range_for(period: str):
    """period in {'today','week','month','year'} -> (date_from, date_to)."""
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


# ---------------------------------------------------------------------------
# PDF export — uses reportlab
# ---------------------------------------------------------------------------

# Amharic font registration is attempted once. If no Ethiopic-capable font
# is found, Amharic characters fall back to the product CODE rather than
# the localized name (so the PDF never crashes or shows tofu boxes).
_FONT_REGISTERED = None  # (regular_name, bold_name) or False


def _register_amharic_font():
    """Try to register an Ethiopic-capable Unicode font with reportlab.
    Returns a tuple (regular, bold) of font names, or False if not available."""
    global _FONT_REGISTERED
    if _FONT_REGISTERED is not None:
        return _FONT_REGISTERED

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    # Common locations for Ethiopic-capable fonts on Windows / Linux / Mac
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
                    bold_name = name  # use regular as bold fallback
                _FONT_REGISTERED = (name, bold_name)
                return _FONT_REGISTERED
        except Exception:
            continue

    _FONT_REGISTERED = False
    return False


def _amharic_safe(text: str, fallback: str) -> str:
    """If we don't have an Ethiopic font, replace any Ethiopic character
    string with the provided fallback (typically a product code)."""
    if _register_amharic_font():
        return text
    # Detect any Ethiopic codepoint (U+1200..U+137F)
    if any('\u1200' <= ch <= '\u137F' for ch in (text or "")):
        return fallback
    return text


def export_pdf(report_type: str, date_from: str, date_to: str, out_path: str,
               customer: str = None):
    """
    report_type: 'production' | 'materials' | 'sales' | 'finished' | 'combined'
    customer:    if set, restricts the sales section to this customer.
    Saves a PDF and returns the file path.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, PageBreak)

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

    # ---------- Production: split per category ------------------------------
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

    # ---------- Material Usage ---------------------------------------------
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

    # ---------- Sales: split per category ----------------------------------
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

    # ---------- Finished Goods --------------------------------------------
    if report_type in ("finished", "combined"):
        rows = finished_goods_report(date_from, date_to)
        # Split by category in PDF too
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


# ---------------------------------------------------------------------------
# v3 reporting: profit, worker performance, expense summary
# ---------------------------------------------------------------------------

def profit_summary(date_from: str, date_to: str):
    """Returns gross + net profit numbers over the period.
    gross_profit = revenue - cost_of_sales
    net_profit   = gross_profit - total_operating_expenses
    """
    from app.services import expense_service
    conn = get_connection()
    try:
        r = conn.execute(
            """SELECT COALESCE(SUM(total),0)      AS revenue,
                      COALESCE(SUM(cost_total),0) AS cost
                FROM sales
                WHERE sale_date BETWEEN ? AND ?
                  AND deleted_at IS NULL""",
            (date_from, date_to),
        ).fetchone()
        revenue = r["revenue"] or 0
        cost = r["cost"] or 0
        gross = revenue - cost
        opex = expense_service.total_expenses(date_from, date_to)
        return {
            "revenue": revenue,
            "cost_of_sales": cost,
            "gross_profit": gross,
            "operating_expenses": opex,
            "net_profit": gross - opex,
            "margin_pct": (gross / revenue * 100) if revenue > 0 else 0,
        }
    finally:
        conn.close()


def profit_by_product(date_from: str, date_to: str):
    """Profit broken down per product for the period."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT pr.code, pr.name, pr.category, pr.input_unit,
                      SUM(s.quantity)   AS qty_sold,
                      SUM(s.total)      AS revenue,
                      SUM(s.cost_total) AS cost,
                      SUM(s.total) - SUM(s.cost_total) AS profit
                 FROM sales s
                 JOIN products pr ON pr.id = s.product_id
                WHERE s.sale_date BETWEEN ? AND ?
                  AND s.deleted_at IS NULL
             GROUP BY pr.code, pr.name, pr.category, pr.input_unit
             ORDER BY profit DESC""",
            (date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def worker_performance(date_from: str, date_to: str):
    """Per-worker production output over the period, broken by category."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT COALESCE(NULLIF(TRIM(p.made_by),''),'(unknown)') AS made_by,
                      pr.category, pr.input_unit,
                      SUM(p.quantity) AS total_qty,
                      COUNT(*) AS runs
                 FROM production p
                 JOIN products pr ON pr.id = p.product_id
                WHERE p.production_date BETWEEN ? AND ?
                  AND p.deleted_at IS NULL
             GROUP BY made_by, pr.category, pr.input_unit
             ORDER BY made_by, pr.category""",
            (date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
