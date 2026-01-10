from django.db import transaction
from django.utils import timezone
from core.models import DocumentSequence, DocumentType


class InvoiceNumberGenerator:
    @staticmethod
    def generate_invoice_number(company, doc_type):
        """
        Generates: PREFIX-YEAR-SEQUENCE
        Example: INV-2026-00001
        """
        now = timezone.now()
        current_year = now.year

        PREFIX = {
            DocumentType.PURCHASE_ORDER: 'PINV',
            DocumentType.PURCHASE_RETURN: 'PRN',
            DocumentType.SALES_ORDER: 'INV',
            DocumentType.SALES_RETURN: 'SRN',
        }
        with transaction.atomic():
            # Lock the row for this specific Month and Year
            sequence, created = DocumentSequence.objects.select_for_update().get_or_create(
                company=company,
                document_type=doc_type,
                current_year=current_year,
                defaults={}
            )

            # Get prefix from dictionary
            prefix = PREFIX.get(doc_type, 'DOC')

            # Format: INV-2026-00001
            seq_str = str(sequence.next_number).zfill(5)

            number_str = f"{prefix}-{sequence.current_year}-{seq_str}"

            sequence.next_number += 1
            sequence.save()

            return number_str
