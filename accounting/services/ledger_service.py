"""
Accounting Ledger Service
Handles double-entry accounting ledger creation for business transactions.

Industry Standard Double-Entry Accounting:
- Every transaction must have equal debits and credits
- Assets and Expenses: Debit increases, Credit decreases
- Liabilities, Equity, and Revenue: Credit increases, Debit decreases
"""
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.db import transaction as db_transaction
from accounting.models import Ledger, TransactionType


class LedgerService:
    """
    Service for creating accounting ledger entries following double-entry principles.
    """

    @staticmethod
    def create_purchase_ledger_entry(purchase, company):
        """
        Create a single ledger entry for a purchase transaction.

        Single-Entry Accounting:
        - Debit: Supplier Payable (what we owe) = grand_total
        - Balance = Previous Balance + Debit (Purchase) - Credit (Payment)
        - Due amount is a positive number (amount we owe to supplier)

        Args:
            purchase: Purchase instance
            company: Company instance

        Returns:
            Ledger instance
        """
        content_type = ContentType.objects.get_for_model(purchase)
        party = purchase.supplier  # Supplier is a proxy of Party

        description = f"Purchase Invoice {purchase.invoice_number}"
        if purchase.notes:
            description += f" - {purchase.notes[:100]}"

        # Single entry: Supplier Payable (Debit - increases what we owe)
        ledger_entry = Ledger.objects.create(
            company=company,
            party=party,
            content_type=content_type,
            object_id=purchase.id,
            date=purchase.invoice_date,
            txn_id=purchase.invoice_number or f"PUR-{purchase.id}",
            txn_type=TransactionType.PURCHASE,
            description=description,
            debit=purchase.grand_total,
            credit=Decimal('0.00')
        )

        return ledger_entry

    @staticmethod
    def create_sale_ledger_entry(sale, company):
        """
        Create a single ledger entry for a sale transaction.

        Single-Entry Accounting:
        - Debit: Customer Receivable (Asset) = grand_total

        Args:
            sale: Sale instance
            company: Company instance

        Returns:
            Ledger instance
        """
        content_type = ContentType.objects.get_for_model(sale)
        party = sale.customer  # Customer is a proxy of Party

        description = f"Sales Invoice {sale.invoice_number}"
        if sale.notes:
            description += f" - {sale.notes[:100]}"

        # Single entry: Customer Receivable (Debit)
        ledger_entry = Ledger.objects.create(
            company=company,
            party=party,
            content_type=content_type,
            object_id=sale.id,
            date=sale.invoice_date,
            txn_id=sale.invoice_number or f"SAL-{sale.id}",
            txn_type=TransactionType.SALE,
            description=description,
            debit=sale.grand_total,
            credit=Decimal('0.00')
        )

        return ledger_entry

    @staticmethod
    def create_payment_ledger_entry(payment, company, party, payment_type='received', source_object=None):
        """
        Create a single ledger entry for a payment transaction.

        Single-Entry Accounting:
        For Payment Received (from customer):
        - Credit: Customer Receivable (reduces what customer owes us) = amount
        - Balance = Previous Balance + Debit (Sale) - Credit (Payment)
        - Due amount is positive (customer owes us money)

        For Payment Made (to supplier):
        - Credit: Supplier Payable (reduces what we owe supplier) = amount
        - Balance = Previous Balance + Debit (Purchase) - Credit (Payment)
        - Due amount is positive (we owe supplier money)

        Args:
            payment: Payment instance (CustomerPayment or SupplierPayment) or SimpleNamespace with payment data
            company: Company instance
            party: Party instance (Customer or Supplier)
            payment_type: 'received' or 'made'
            source_object: Optional source object (Sale/Purchase) if payment is SimpleNamespace

        Returns:
            tuple: (ledger_entry, ledger_entry) For backward compatibility
        """
        # Handle SimpleNamespace (when payment is created during sale/purchase creation)
        if source_object is not None:
            content_type = ContentType.objects.get_for_model(source_object)
            object_id = source_object.id
        else:
            # Regular payment model instance
            from types import SimpleNamespace
            if isinstance(payment, SimpleNamespace):
                # If SimpleNamespace without source_object, we can't create content_type
                # This shouldn't happen, but handle gracefully
                content_type = None
                object_id = None
            else:
                content_type = ContentType.objects.get_for_model(
                    payment.__class__)
                object_id = payment.id

        description = f"Payment {payment.reference_number}"
        if hasattr(payment, 'notes') and payment.notes:
            description += f" - {payment.notes[:100]}"

        # Handle date conversion
        payment_date = payment.date
        if hasattr(payment_date, 'date'):
            payment_date = payment_date.date()
        elif hasattr(payment_date, '__str__'):
            # Already a date object or string
            pass

        if payment_type == 'received':
            # Payment received from customer
            # Single entry: Customer Receivable (Credit - reduces what customer owes us)
            credit_entry = Ledger.objects.create(
                company=company,
                party=party,
                content_type=content_type,
                object_id=object_id,
                date=payment_date,
                txn_id=payment.reference_number,
                txn_type=TransactionType.PAYMENT_RECEIVED,
                description=description,
                debit=Decimal('0.00'),
                credit=payment.amount
            )
            debit_entry = credit_entry  # For backward compatibility
        else:
            # Payment made to supplier
            # Single entry: Supplier Payable (Credit - reduces what we owe)
            credit_entry = Ledger.objects.create(
                company=company,
                party=party,
                content_type=content_type,
                object_id=object_id,
                date=payment_date,
                txn_id=payment.reference_number,
                txn_type=TransactionType.PAYMENT_MADE,
                description=description,
                debit=Decimal('0.00'),
                credit=payment.amount
            )
            debit_entry = credit_entry  # For backward compatibility

        return debit_entry, credit_entry

    @staticmethod
    def delete_ledger_entries_for_object(obj, company):
        """
        Delete all ledger entries associated with a given object.
        Used when deleting or reverting transactions.

        Args:
            obj: Model instance (Purchase, Sale, Payment, etc.)
            company: Company instance
        """
        content_type = ContentType.objects.get_for_model(obj.__class__)
        Ledger.objects.filter(
            company=company,
            content_type=content_type,
            object_id=obj.id
        ).delete()

    @staticmethod
    def create_or_update_opening_balance_entry(party, company, opening_balance):
        """
        Create or update opening balance ledger entry for a party.

        If opening_balance > 0:
        - For Customers: Debit entry (what customer owes us)
        - For Suppliers: Debit entry (what we owe supplier)

        If opening_balance already exists, update it. Otherwise create new entry.

        Args:
            party: Party instance
            company: Company instance
            opening_balance: Decimal amount (from party.opening_balance)
        """
        from core.models import Party as PartyModel

        if opening_balance is None or opening_balance == 0:
            # Delete existing opening balance entry if opening_balance is 0
            Ledger.objects.filter(
                company=company,
                party=party,
                txn_type=TransactionType.OPENING_BALANCE
            ).delete()
            return None

        # Check if opening balance entry already exists
        existing_entry = Ledger.objects.filter(
            company=company,
            party=party,
            txn_type=TransactionType.OPENING_BALANCE
        ).first()

        if existing_entry:
            # Update existing entry
            existing_entry.debit = abs(
                opening_balance) if opening_balance > 0 else Decimal('0.00')
            existing_entry.credit = abs(
                opening_balance) if opening_balance < 0 else Decimal('0.00')
            existing_entry.description = f"Opening Balance - {party.name}"
            existing_entry.save()
            return existing_entry
        else:
            # Create new entry
            # Use party creation date or earliest date for opening balance
            from datetime import date
            opening_date = party.created_at.date() if hasattr(
                party, 'created_at') else date.today()

            return Ledger.objects.create(
                company=company,
                party=party,
                content_type=None,  # Opening balance is not linked to a specific object
                object_id=None,
                date=opening_date,
                txn_id=f"OB-{party.id}",
                txn_type=TransactionType.OPENING_BALANCE,
                description=f"Opening Balance - {party.name}",
                debit=abs(opening_balance) if opening_balance > 0 else Decimal(
                    '0.00'),
                credit=abs(
                    opening_balance) if opening_balance < 0 else Decimal('0.00')
            )

    @staticmethod
    def update_party_balance(party, company):
        """
        Calculate and update party balance from ledger entries.
        Balance = Opening Balance + Sum of (Debits - Credits) for the party.

        This is typically called after ledger entries are created/updated.

        Args:
            party: Party instance
            company: Company instance
        """
        ledger_entries = Ledger.objects.filter(company=company, party=party)

        total_debit = sum(entry.debit for entry in ledger_entries)
        total_credit = sum(entry.credit for entry in ledger_entries)

        # Balance = Debits - Credits (includes opening balance if ledger entry exists)
        # If opening balance ledger entry doesn't exist, add party.opening_balance
        has_opening_balance_entry = any(
            entry.txn_type == TransactionType.OPENING_BALANCE
            for entry in ledger_entries
        )

        if not has_opening_balance_entry:
            # Add opening balance from party model if no ledger entry exists
            balance = party.opening_balance + (total_debit - total_credit)
        else:
            # Opening balance already included in ledger entries
            balance = total_debit - total_credit

        # Update party balance
        from core.models import Party as PartyModel
        PartyModel.objects.filter(
            id=party.id, company=company).update(balance=balance)
