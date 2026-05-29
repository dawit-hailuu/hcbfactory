"""Print a small customer receipt for a single sale."""
from pathlib import Path
from datetime import datetime
from app.services import sales_service


def export_receipt(sale_id: int, out_path: str):
    """Generate a simple PDF receipt for the given sale."""
    sale = sales_service.get_sale(sale_id)
    if sale is None:
        raise ValueError("Sale not found")

    from reportlab.lib.pagesizes import A5
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle)
    # Reuse Amharic font auto-registration from report_service
    from app.services.report_service import _register_amharic_font, _amharic_safe
    font = _register_amharic_font()
    base = font[0] if font else "Helvetica"
    bold = font[1] if font else "Helvetica-Bold"

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(out_path, pagesize=A5,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet()
    title  = ParagraphStyle("t", parent=styles["Heading1"], fontSize=16,
                            textColor=colors.HexColor("#1F4E79"),
                            fontName=bold, alignment=1)
    sub    = ParagraphStyle("s", parent=styles["Normal"], fontSize=10,
                            textColor=colors.grey, alignment=1, fontName=base)
    body   = ParagraphStyle("b", parent=styles["Normal"], fontSize=10, fontName=base)
    total_st = ParagraphStyle("tot", parent=styles["Normal"], fontSize=13,
                              fontName=bold, alignment=2)

    story = []
    story.append(Paragraph("MN Construction", title))
    story.append(Paragraph("Sales Receipt", sub))
    story.append(Spacer(1, 8))

    story.append(Paragraph(f"<b>Receipt #</b>: {sale_id}", body))
    story.append(Paragraph(f"<b>Date</b>: {sale['sale_date']}", body))
    story.append(Paragraph(f"<b>Customer</b>: {sale.get('customer_name') or '—'}", body))
    story.append(Spacer(1, 10))

    unit = "pieces" if sale["input_unit"] == "piece" else "m²"
    product_text = _amharic_safe(
        f"{sale['product_code']} — {sale['product_name']}",
        sale["product_code"]
    )
    table_data = [
        ["Product", "Qty", "Unit", "Unit Price (ETB)", "Total (ETB)"],
        [product_text,
         f"{sale['quantity']:.2f}", unit,
         f"{sale['unit_price']:,.2f}",
         f"{sale['total']:,.2f}"],
    ]
    t = Table(table_data, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), bold),
        ("FONTNAME",   (0,1), (-1,-1), base),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("GRID",       (0,0), (-1,-1), 0.25, colors.grey),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))

    paid = sale.get("amount_paid") or sale["total"]
    bal = sale["total"] - paid
    story.append(Paragraph(f"Total: {sale['total']:,.2f} ETB", total_st))
    story.append(Paragraph(f"Paid:  {paid:,.2f} ETB", total_st))
    if bal > 0:
        story.append(Paragraph(
            f'<font color="#C0392B">Balance due: {bal:,.2f} ETB</font>', total_st))
    else:
        story.append(Paragraph(
            f'<font color="#27AE60">Paid in full</font>', total_st))

    story.append(Spacer(1, 24))
    story.append(Paragraph(
        f"<i>Issued: {datetime.now():%Y-%m-%d %H:%M}. Thank you for your business.</i>",
        sub))

    doc.build(story)
    return out_path
