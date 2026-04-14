"""
Generate a dummy PDF invoice for testing the extraction pipeline.

This creates a realistic shipping/logistics invoice using reportlab.
We use reportlab because it creates actual PDFs (not just text files renamed as .pdf),
which tests Docling's real parsing capabilities.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
import os

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "input_docs", "INV-2024-0042.pdf")


def generate_dummy_invoice(output_path: str = OUTPUT_PATH) -> str:
    """Generate a realistic freight invoice PDF and return its path."""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(
        name="CompanyHeader",
        fontSize=18,
        textColor=colors.HexColor("#1a365d"),
        spaceAfter=2,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="Address",
        fontSize=9,
        textColor=colors.grey,
        spaceAfter=1,
        fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle",
        fontSize=11,
        textColor=colors.HexColor("#2d3748"),
        spaceBefore=12,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="Label",
        fontSize=8,
        textColor=colors.grey,
        fontName="Helvetica-Oblique",
    ))
    styles.add(ParagraphStyle(
        name="Value",
        fontSize=10,
        textColor=colors.black,
        fontName="Helvetica",
        spaceAfter=2,
    ))

    story = []

    # ── Company Header ──
    story.append(Paragraph("Shanghai Global Freight Co., Ltd.", styles["CompanyHeader"]))
    story.append(Paragraph("No. 888 Pudong Avenue, Shanghai, China 200120", styles["Address"]))
    story.append(Paragraph("Tel: +86-21-5555-0199 | Email: billing@shanghaiglobalfreight.cn", styles["Address"]))
    story.append(Spacer(1, 15))

    # ── Invoice Details Grid ──
    story.append(Paragraph("INVOICE", styles["SectionTitle"]))

    invoice_info_data = [
        [Paragraph("<b>Invoice Number:</b>", styles["Value"]),
         Paragraph("INV-2024-0042", styles["Value"]),
         Paragraph("<b>Invoice Date:</b>", styles["Value"]),
         Paragraph("March 15, 2024", styles["Value"])],
        [Paragraph("<b>Bill To:</b>", styles["Value"]),
         Paragraph("Pacific Rim Logistics LLC\n1200 Harbor Gateway Blvd\nLos Angeles, CA 90710", styles["Value"]),
         Paragraph("<b>Payment Terms:</b>", styles["Value"]),
         Paragraph("Net 30", styles["Value"])],
    ]

    info_table = Table(invoice_info_data, colWidths=[1.3*inch, 2.2*inch, 1.3*inch, 2.2*inch])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 8))

    # ── Shipment Details ──
    story.append(Paragraph("Shipment Details", styles["SectionTitle"]))

    shipment_data = [
        [Paragraph("<b>Origin:</b>", styles["Value"]), Paragraph("Shanghai, China (Port of Loading)", styles["Value"])],
        [Paragraph("<b>Destination:</b>", styles["Value"]), Paragraph("Los Angeles, CA, USA (Port of Discharge)", styles["Value"])],
        [Paragraph("<b>Incoterms:</b>", styles["Value"]), Paragraph("FOB Shanghai", styles["Value"])],
        [Paragraph("<b>Vessel:</b>", styles["Value"]), Paragraph("COSCO Star V.2403E", styles["Value"])],
        [Paragraph("<b>Container Count:</b>", styles["Value"]), Paragraph("20 x 40ft Dry Containers", styles["Value"])],
    ]

    shipment_table = Table(shipment_data, colWidths=[1.5*inch, 5.5*inch])
    shipment_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-2, -1), 0.5, colors.lightgrey),
    ]))
    story.append(shipment_table)
    story.append(Spacer(1, 10))

    # ── Line Items Table ──
    story.append(Paragraph("Line Items", styles["SectionTitle"]))

    line_items = [
        [Paragraph("<b>Description</b>", styles["Value"]),
         Paragraph("<b>Qty</b>", styles["Value"]),
         Paragraph("<b>Unit Price (USD)</b>", styles["Value"]),
         Paragraph("<b>Total (USD)</b>", styles["Value"])],
        [Paragraph("Ocean Freight — Shanghai to Los Angeles\n(40ft Dry Container)", styles["Value"]),
         Paragraph("20", styles["Value"]),
         Paragraph("1,500.00", styles["Value"]),
         Paragraph("30,000.00", styles["Value"])],
        [Paragraph("Terminal Handling Charge (Origin)", styles["Value"]),
         Paragraph("20", styles["Value"]),
         Paragraph("150.00", styles["Value"]),
         Paragraph("3,000.00", styles["Value"])],
        [Paragraph("Documentation & Customs Filing", styles["Value"]),
         Paragraph("1", styles["Value"]),
         Paragraph("250.00", styles["Value"]),
         Paragraph("250.00", styles["Value"])],
        [Paragraph("Fuel Surcharge (BAF)", styles["Value"]),
         Paragraph("20", styles["Value"]),
         Paragraph("120.00", styles["Value"]),
         Paragraph("2,400.00", styles["Value"])],
    ]

    items_table = Table(line_items, colWidths=[3.0*inch, 1.0*inch, 1.5*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        # Data rows
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
        # Alignment
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 10))

    # ── Totals ──
    story.append(Paragraph("Total Amount Due", styles["SectionTitle"]))

    totals_data = [
        [Paragraph("Subtotal:", styles["Value"]), Paragraph("$35,650.00", styles["Value"])],
        [Paragraph("Tax (0% — Export):", styles["Value"]), Paragraph("$0.00", styles["Value"])],
        [Paragraph("<b>Total Due (USD):</b>", styles["Value"]), Paragraph("<b>$35,650.00</b>", styles["Value"])],
    ]

    totals_table = Table(totals_data, colWidths=[4.5*inch, 2.5*inch])
    totals_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, 2), (-1, 2), 2, colors.black),
        ("LINEABOVE", (0, 0), (-1, 0), 1, colors.lightgrey),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.lightgrey),
        ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.lightgrey),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 15))

    # ── Footer ──
    story.append(Spacer(1, 20))
    story.append(Paragraph("— End of Invoice —", ParagraphStyle(
        "Footer", fontSize=9, textColor=colors.grey, alignment=TA_CENTER, fontName="Helvetica-Oblique"
    )))

    doc.build(story)
    print(f"✅ Dummy invoice generated: {output_path}")
    return output_path


if __name__ == "__main__":
    generate_dummy_invoice()
