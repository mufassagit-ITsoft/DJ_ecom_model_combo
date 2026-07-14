"""
payment/invoice.py

Generates a PDF invoice receipt for a completed Gamestore order
using ReportLab. Returns the PDF as bytes so it can be attached
to an email without writing to disk.

Usage:
    from payment.invoice import generate_invoice_pdf
    pdf_bytes = generate_invoice_pdf(order, order_items, rewards_earned, rewards_redeemed)
"""

from io import BytesIO
from decimal import Decimal

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER


# Brand colours (Mario NES palette) 
NAVY   = colors.HexColor('#1F3864')
GOLD   = colors.HexColor('#F8B800')
RED    = colors.HexColor('#C00000')
GREEN  = colors.HexColor('#28a745')
LGREY  = colors.HexColor('#F2F2F2')
DGREY  = colors.HexColor('#555555')
BLACK  = colors.black
WHITE  = colors.white


def generate_invoice_pdf(order, order_items, rewards_earned=0, rewards_redeemed=0):
    """
    Generate a PDF invoice receipt for a completed order.

    Args:
        order            : payment.models.Order instance
        order_items      : list or queryset of payment.models.OrderItem instances
        rewards_earned   : float/Decimal — points awarded for this order
        rewards_redeemed : float/Decimal — points that were applied at checkout

    Returns:
        bytes — raw PDF content ready to attach to an email
    """

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()

    # Custom styles 
    brand_title = ParagraphStyle(
        'BrandTitle',
        parent=styles['Normal'],
        fontSize=26,
        textColor=WHITE,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT,
    )
    brand_sub = ParagraphStyle(
        'BrandSub',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#B8C8E0'),
        fontName='Helvetica',
        alignment=TA_LEFT,
    )
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontSize=11,
        textColor=NAVY,
        fontName='Helvetica-Bold',
        spaceBefore=14,
        spaceAfter=4,
    )
    body_text = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontSize=10,
        textColor=DGREY,
        fontName='Helvetica',
        leading=16,
    )
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontSize=10,
        textColor=BLACK,
        fontName='Helvetica-Bold',
        leading=16,
    )
    thank_you = ParagraphStyle(
        'ThankYou',
        parent=styles['Normal'],
        fontSize=13,
        textColor=NAVY,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        spaceBefore=20,
        spaceAfter=4,
    )
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=DGREY,
        fontName='Helvetica',
        alignment=TA_CENTER,
    )

    story = []

    # HEADER BANNER 
    header_data = [[
        Paragraph('evoGames', brand_title),
        Paragraph('INVOICE RECEIPT', ParagraphStyle(
            'InvTitle', parent=brand_title, alignment=TA_RIGHT, fontSize=18,
            textColor=GOLD
        ))
    ]]
    header_table = Table(header_data, colWidths=[3.5 * inch, 3.5 * inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, -1), NAVY),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',  (0, 0), (-1, -1), 18),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 18),
        ('LEFTPADDING', (0, 0), (0, 0), 16),
        ('RIGHTPADDING',(-1, 0),(-1, 0), 16),
    ]))
    story.append(header_table)

    # Tagline below header
    tagline_data = [[
        Paragraph('When you level up, we level up!!!', brand_sub),
        Paragraph('dj-ecom-model-combo.onrender.com', ParagraphStyle(
            'TagRight', parent=brand_sub, alignment=TA_RIGHT
        ))
    ]]
    tagline_table = Table(tagline_data, colWidths=[3.5 * inch, 3.5 * inch])
    tagline_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#141a2e')),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (0, 0), 16),
        ('RIGHTPADDING',  (-1, 0),(-1, 0), 16),
    ]))
    story.append(tagline_table)
    story.append(Spacer(1, 0.25 * inch))

    # THANK YOU MESSAGE 
    story.append(Paragraph(
        f'Thank you for your order, {order.full_name}!',
        thank_you
    ))
    story.append(Paragraph(
        'Your payment was successful and your order is being processed. '
        'Please keep this receipt for your records.',
        ParagraphStyle('CentreBody', parent=body_text, alignment=TA_CENTER,
                       spaceAfter=10)
    ))
    story.append(HRFlowable(width='100%', thickness=2, color=GOLD, spaceAfter=14))

    # ORDER INFO ROW 
    date_str = order.date_ordered.strftime('%B %d, %Y  %I:%M %p') \
        if order.date_ordered else 'N/A'
    order_info_data = [[
        Paragraph(f'<b>Order ID:</b>  #{order.id}', body_text),
        Paragraph(f'<b>Date:</b>  {date_str}', ParagraphStyle(
            'RightBody', parent=body_text, alignment=TA_RIGHT
        )),
    ]]
    order_info_table = Table(order_info_data, colWidths=[3.5 * inch, 3.5 * inch])
    order_info_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), LGREY),
        ('TOPPADDING',    (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 12),
    ]))
    story.append(order_info_table)
    story.append(Spacer(1, 0.2 * inch))

    # BILLING / SHIPPING 
    billing_shipping_data = [[
        Paragraph('<b>Bill To / Ship To</b>', section_heading),
    ]]
    story.append(Paragraph('Bill To / Ship To', section_heading))
    story.append(Paragraph(order.full_name, body_bold))
    story.append(Paragraph(order.email, body_text))
    if order.shipping_address:
        for line in order.shipping_address.strip().split('\n'):
            if line.strip():
                story.append(Paragraph(line.strip(), body_text))
    story.append(Spacer(1, 0.2 * inch))

    # ORDER ITEMS TABLE 
    story.append(Paragraph('Order Items', section_heading))
    story.append(Spacer(1, 6))

    item_header = ['#', 'Product', 'Qty', 'Unit Price', 'Total']
    item_rows   = [item_header]

    subtotal = Decimal('0.00')
    for idx, item in enumerate(order_items, start=1):
        title    = str(item.product.title) if item.product else 'Unknown Product'
        qty      = item.quantity
        price    = Decimal(str(item.price))
        line_tot = price * qty
        subtotal += line_tot
        item_rows.append([
            str(idx),
            title,
            str(qty),
            f'${float(price):.2f}',
            f'${float(line_tot):.2f}',
        ])

    items_table = Table(
        item_rows,
        colWidths=[0.4 * inch, 3.3 * inch, 0.6 * inch, 1.1 * inch, 1.1 * inch],
    )
    items_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND',    (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR',     (0, 0), (-1, 0), WHITE),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0), 10),
        ('ALIGN',         (0, 0), (-1, 0), 'CENTER'),
        ('TOPPADDING',    (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        # Data rows — alternating
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, LGREY]),
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -1), 10),
        ('ALIGN',         (0, 1), (0, -1),  'CENTER'),   # #
        ('ALIGN',         (2, 1), (2, -1),  'CENTER'),   # Qty
        ('ALIGN',         (3, 1), (-1, -1), 'RIGHT'),    # Price / Total
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('LEFTPADDING',   (1, 0), (1, -1),  8),
        # Grid
        ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 0.2 * inch))

    # TOTALS BLOCK 
    totals_rows = []

    if Decimal(str(rewards_redeemed)) > 0:
        totals_rows.append([
            Paragraph('Subtotal:', body_text),
            Paragraph(f'${float(subtotal):.2f}', ParagraphStyle(
                'RR', parent=body_text, alignment=TA_RIGHT))
        ])
        totals_rows.append([
            Paragraph('Rewards Applied:', ParagraphStyle(
                'GreenLabel', parent=body_text, textColor=GREEN)),
            Paragraph(f'-${float(rewards_redeemed):.2f}', ParagraphStyle(
                'GreenVal', parent=body_text, alignment=TA_RIGHT, textColor=GREEN))
        ])

    totals_rows.append([
        Paragraph('<b>Amount Paid:</b>', ParagraphStyle(
            'TotalLabel', parent=body_text, fontName='Helvetica-Bold',
            fontSize=12, textColor=NAVY)),
        Paragraph(f'<b>${float(order.amount_paid):.2f}</b>', ParagraphStyle(
            'TotalVal', parent=body_text, fontName='Helvetica-Bold',
            fontSize=12, textColor=NAVY, alignment=TA_RIGHT))
    ])

    totals_rows.append([
        Paragraph('Payment Method:', body_text),
        Paragraph('PayPal', ParagraphStyle(
            'PPRight', parent=body_text, alignment=TA_RIGHT))
    ])

    if order.paypal_transaction_id:
        totals_rows.append([
            Paragraph('PayPal Transaction ID:', body_text),
            Paragraph(str(order.paypal_transaction_id), ParagraphStyle(
                'PPIDRight', parent=body_text, alignment=TA_RIGHT,
                textColor=DGREY, fontSize=8))
        ])

    totals_table = Table(
        totals_rows,
        colWidths=[4.0 * inch, 3.0 * inch],
        hAlign='RIGHT',
    )
    totals_table.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEABOVE',     (0, -len(totals_rows)), (-1, -len(totals_rows)),
         1.5, GOLD),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 0.15 * inch))

    # REWARDS EARNED BANNER 
    if Decimal(str(rewards_earned)) > 0:
        rewards_data = [[
            Paragraph(
                f'&#9733;  You earned <b>${float(rewards_earned):.2f}</b> in rewards '
                f'points on this order!  &#9733;',
                ParagraphStyle('RewardsMsg', parent=body_text, alignment=TA_CENTER,
                               textColor=colors.HexColor('#856404'), fontName='Helvetica-Bold',
                               fontSize=11)
            )
        ]]
        rewards_banner = Table(rewards_data, colWidths=[7 * inch])
        rewards_banner.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#fff3cd')),
            ('TOPPADDING',    (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING',   (0, 0), (-1, -1), 12),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 12),
            ('BOX',           (0, 0), (-1, -1), 1, colors.HexColor('#ffc107')),
        ]))
        story.append(rewards_banner)
        story.append(Spacer(1, 0.15 * inch))

    # FOOTER 
    story.append(HRFlowable(width='100%', thickness=1, color=LGREY, spaceBefore=20))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'evoGames LLC  |  dj-ecom-model-combo.onrender.com',
        footer_style
    ))
    story.append(Paragraph(
        'Thank you for shopping with us. For questions, contact us via our website.',
        footer_style
    ))
    story.append(Paragraph(
        'This is an automatically generated receipt. Please retain for your records.',
        ParagraphStyle('FooterItalic', parent=footer_style, fontSize=7,
                       textColor=colors.HexColor('#AAAAAA'))
    ))

    # BUILD 
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes