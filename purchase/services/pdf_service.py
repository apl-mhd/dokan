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


class PurchaseInvoicePDF:
    """Generate professional PDF invoices for purchases using HTML template"""

    def __init__(self, purchase):
        self.purchase = purchase

    def _prepare_context(self):
        """Prepare context data for the invoice template"""
        # Calculate due amount
        due_amount = self.purchase.grand_total - self.purchase.paid_amount

        # Determine status
        if self.purchase.paid_amount and due_amount:
            status = 'Partial' if due_amount > 0 else 'Paid'
        elif due_amount and due_amount > 0:
            status = 'Due'
        else:
            status = 'Paid'

        # Calculate tax rate if tax exists
        tax_rate = None
        if self.purchase.tax and self.purchase.sub_total:
            try:
                tax_rate = (self.purchase.tax / self.purchase.sub_total) * 100
            except (ZeroDivisionError, TypeError):
                tax_rate = None

        # Prepare invoice object for template
        invoice = type('Invoice', (), {
            'invoice_no': self.purchase.invoice_number or f'PINV-{self.purchase.id}',
            'invoice_date': self.purchase.invoice_date,
            'due_date': None,  # Purchase model doesn't have due_date
            'invoice_type': 'purchase',
            'status': status,
            'paid_amount': self.purchase.paid_amount,
            'due_amount': due_amount,
            'sub_total': self.purchase.sub_total,
            'discount_amount': self.purchase.discount,
            'tax_rate': tax_rate,
            'tax_amount': self.purchase.tax,
            'delivery_charge': self.purchase.delivery_charge,
            'grand_total': self.purchase.grand_total,
            'amount_in_words': None,  # Can be added later if needed
            'notes': self.purchase.notes,
        })()

        # Prepare company object
        if not self.purchase.company:
            raise ValueError("Purchase must have a company")
        company = type('Company', (), {
            'name': getattr(self.purchase.company, 'name', ''),
            'address': getattr(self.purchase.company, 'address', '') or '',
            'phone': getattr(self.purchase.company, 'phone', '') or '',
            'email': getattr(self.purchase.company, 'email', '') or '',
        })()

        # Prepare party (supplier) object
        if not self.purchase.supplier:
            raise ValueError("Purchase must have a supplier")
        party = type('Party', (), {
            'name': getattr(self.purchase.supplier, 'name', ''),
            'address': getattr(self.purchase.supplier, 'address', '') or '',
            'phone': getattr(self.purchase.supplier, 'phone', '') or '',
        })()

        # Prepare items
        items = []
        for item in self.purchase.items.all():
            if not item.product:
                raise ValueError(
                    f"Purchase item {item.id} must have a product")
            if not item.unit:
                raise ValueError(f"Purchase item {item.id} must have a unit")
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
        filename = f"purchase_invoice_{self.purchase.invoice_number or self.purchase.id}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write(pdf_value)

        return response
