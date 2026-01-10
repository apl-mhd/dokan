from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from django.http import HttpResponse
from io import BytesIO
from datetime import datetime


class PurchaseInvoicePDF:
    """Generate professional PDF invoices for purchases"""
    
    def __init__(self, purchase):
        self.purchase = purchase
        self.buffer = BytesIO()
        self.pagesize = A4
        self.width, self.height = self.pagesize
        
    def generate(self):
        """Generate the PDF and return HttpResponse"""
        # Create the PDF object
        pdf = SimpleDocTemplate(
            self.buffer,
            pagesize=self.pagesize,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
        )
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=1  # Center
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=12,
        )
        
        normal_style = styles['Normal']
        
        # Title
        title = Paragraph(f"PURCHASE INVOICE", title_style)
        elements.append(title)
        elements.append(Spacer(1, 0.2*inch))
        
        # Invoice Info Table
        invoice_data = [
            ['Invoice Number:', self.purchase.invoice_number or f'PINV-{self.purchase.id}'],
            ['Invoice Date:', self.purchase.invoice_date.strftime('%B %d, %Y')],
            ['Status:', self.purchase.status.upper()],
        ]
        
        invoice_table = Table(invoice_data, colWidths=[2*inch, 3*inch])
        invoice_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2c3e50')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(invoice_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Company and Supplier Info (Side by side)
        info_data = [
            [
                Paragraph('<b>From:</b><br/>' + 
                         f'{self.purchase.company.name}<br/>' +
                         f'{self.purchase.warehouse.name}<br/>' +
                         f'{self.purchase.warehouse.location or ""}',
                         normal_style),
                Paragraph('<b>Supplier:</b><br/>' +
                         f'{self.purchase.supplier.name}<br/>' +
                         f'{self.purchase.supplier.address or ""}<br/>' +
                         f'Phone: {self.purchase.supplier.phone or "N/A"}',
                         normal_style)
            ]
        ]
        
        info_table = Table(info_data, colWidths=[3.5*inch, 3.5*inch])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.4*inch))
        
        # Items Table Header
        elements.append(Paragraph('ITEMS', heading_style))
        
        # Items Table
        items_data = [['#', 'Product', 'Quantity', 'Unit', 'Unit Price', 'Total']]
        
        for idx, item in enumerate(self.purchase.items.all(), 1):
            items_data.append([
                str(idx),
                item.product.name,
                f'{float(item.quantity):.2f}',
                item.unit.name,
                f'৳{float(item.unit_price):,.2f}',
                f'৳{float(item.line_total):,.2f}'
            ])
        
        items_table = Table(items_data, colWidths=[0.5*inch, 3*inch, 1*inch, 1*inch, 1.2*inch, 1.3*inch])
        items_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # # column
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),    # Product column
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Numeric columns
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Totals
        totals_data = [
            ['', '', '', '', 'Grand Total:', f'৳{float(self.purchase.grand_total):,.2f}']
        ]
        
        totals_table = Table(totals_data, colWidths=[0.5*inch, 3*inch, 1*inch, 1*inch, 1.2*inch, 1.3*inch])
        totals_table.setStyle(TableStyle([
            ('FONTNAME', (4, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (4, 0), (-1, 0), 12),
            ('ALIGN', (4, 0), (-1, 0), 'RIGHT'),
            ('TEXTCOLOR', (4, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('LINEABOVE', (4, 0), (-1, 0), 2, colors.HexColor('#2c3e50')),
            ('TOPPADDING', (4, 0), (-1, 0), 10),
        ]))
        elements.append(totals_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Notes
        if self.purchase.notes:
            elements.append(Paragraph('<b>Notes:</b>', normal_style))
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(self.purchase.notes, normal_style))
            elements.append(Spacer(1, 0.3*inch))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=1  # Center
        )
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph(
            f'Generated on {datetime.now().strftime("%B %d, %Y at %I:%M %p")}',
            footer_style
        ))
        elements.append(Paragraph('Thank you for your business!', footer_style))
        
        # Build PDF
        pdf.build(elements)
        
        # Get the value of the BytesIO buffer and return response
        pdf_value = self.buffer.getvalue()
        self.buffer.close()
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="purchase_invoice_{self.purchase.invoice_number or self.purchase.id}.pdf"'
        response.write(pdf_value)
        
        return response

