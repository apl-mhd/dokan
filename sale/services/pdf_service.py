from django.http import HttpResponse
from django.template.loader import render_to_string
from io import BytesIO


try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    try:
        from xhtml2pdf import pisa
        XHTML2PDF_AVAILABLE = True
        WEASYPRINT_AVAILABLE = False
    except ImportError:
        WEASYPRINT_AVAILABLE = False
        XHTML2PDF_AVAILABLE = False


class SaleInvoicePDF:
    """Generate professional PDF invoices for sales using HTML template"""

    def __init__(self, sale):
        self.sale = sale

    def _prepare_context(self):
        """Prepare context data for the invoice template"""
        # Calculate due amount
        due_amount = self.sale.grand_total - self.sale.paid_amount

        # Determine status
        if self.sale.paid_amount and due_amount:
            status = 'Partial' if due_amount > 0 else 'Paid'
        elif due_amount and due_amount > 0:
            status = 'Due'
        else:
            status = 'Paid'

        # Calculate tax rate if tax exists
        tax_rate = None
        if self.sale.tax and self.sale.sub_total:
            try:
                tax_rate = (self.sale.tax / self.sale.sub_total) * 100
            except (ZeroDivisionError, TypeError):
                tax_rate = None

        # Prepare invoice object for template
        invoice = type('Invoice', (), {
            'invoice_no': self.sale.invoice_number or f'INV-{self.sale.id}',
            'invoice_date': self.sale.invoice_date,
            'due_date': None,  # Sale model doesn't have due_date
            'invoice_type': 'sale',
            'status': status,
            'paid_amount': self.sale.paid_amount,
            'due_amount': due_amount,
            'sub_total': self.sale.sub_total,
            'discount_amount': self.sale.discount,
            'tax_rate': tax_rate,
            'tax_amount': self.sale.tax,
            'delivery_charge': self.sale.delivery_charge,
            'grand_total': self.sale.grand_total,
            'amount_in_words': None,  # Can be added later if needed
            'notes': self.sale.notes,
        })()

        # Prepare company object
        if not self.sale.company:
            raise ValueError("Sale must have a company")
        company = type('Company', (), {
            'name': getattr(self.sale.company, 'name', ''),
            'address': getattr(self.sale.company, 'address', '') or '',
            'phone': getattr(self.sale.company, 'phone', '') or '',
            'email': getattr(self.sale.company, 'email', '') or '',
        })()

        # Prepare party (customer) object
        if not self.sale.customer:
            raise ValueError("Sale must have a customer")
        party = type('Party', (), {
            'name': getattr(self.sale.customer, 'name', ''),
            'address': getattr(self.sale.customer, 'address', '') or '',
            'phone': getattr(self.sale.customer, 'phone', '') or '',
        })()

        # Prepare items
        items = []
        for item in self.sale.items.all():
            if not item.product:
                raise ValueError(f"Sale item {item.id} must have a product")
            if not item.unit:
                raise ValueError(f"Sale item {item.id} must have a unit")
            item_obj = type('Item', (), {
                'product': type('Product', (), {
                    'name': getattr(item.product, 'name', ''),
                    'sku': getattr(item.product, 'sku', None) or '-',
                })(),
                'quantity': item.quantity,
                'unit': type('Unit', (), {
                    'name': getattr(item.unit, 'name', ''),
                })(),
                'unit_price': item.unit_price,
                'line_total': item.line_total,
            })()
            items.append(item_obj)

        return {
            'invoice': invoice,
            'company': company,
            'party': party,
            'items': items,
        }

    def generate(self):
        """Generate the PDF and return HttpResponse"""
        if not WEASYPRINT_AVAILABLE and not XHTML2PDF_AVAILABLE:
            raise ImportError(
                "Either 'weasyprint' or 'xhtml2pdf' is required for PDF generation. "
                "Please install one: pip install weasyprint or pip install xhtml2pdf"
            )

        # Prepare context
        context = self._prepare_context()

        # Render HTML template
        html_string = render_to_string('invoices/invoice.html', context)

        # Convert HTML to PDF
        buffer = BytesIO()

        if WEASYPRINT_AVAILABLE:
            HTML(string=html_string).write_pdf(buffer)
        else:
            # Use xhtml2pdf
            pisa_status = pisa.CreatePDF(
                html_string,
                dest=buffer
            )
            if pisa_status.err:
                raise Exception("Error generating PDF with xhtml2pdf")

        buffer.seek(0)
        pdf_value = buffer.getvalue()
        buffer.close()

        # Create HTTP response
        response = HttpResponse(content_type='application/pdf')
        filename = f"invoice_{self.sale.invoice_number or self.sale.id}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write(pdf_value)

        return response
