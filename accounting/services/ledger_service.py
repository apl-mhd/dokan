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
        Create ledger entries for a purchase transaction.
        
        Double-Entry Accounting:
        - Debit: Purchase Account (Expense) = grand_total
        - Credit: Supplier Payable (Liability) = grand_total
        
        Args:
            purchase: Purchase instance
            company: Company instance
            
        Returns:
            tuple: (debit_entry, credit_entry) Ledger instances
        """
        content_type = ContentType.objects.get_for_model(purchase)
        party = purchase.supplier  # Supplier is a proxy of Party
        
        description = f"Purchase Invoice {purchase.invoice_number}"
        if purchase.notes:
            description += f" - {purchase.notes[:100]}"
        
        # Debit: Purchase Expense Account
        debit_entry = Ledger.objects.create(
            company=company,
            party=party,
            content_type=content_type,
            object_id=purchase.id,
            date=purchase.invoice_date,
            txn_id=purchase.invoice_number or f"PUR-{purchase.id}",
            txn_type=TransactionType.PURCHASE,
            description=f"{description} - Purchase Expense",
            debit=purchase.grand_total,
            credit=Decimal('0.00')
        )
        
        # Credit: Supplier Payable Account
        credit_entry = Ledger.objects.create(
            company=company,
            party=party,
            content_type=content_type,
            object_id=purchase.id,
            date=purchase.invoice_date,
            txn_id=purchase.invoice_number or f"PUR-{purchase.id}",
            txn_type=TransactionType.PURCHASE,
            description=f"{description} - Supplier Payable",
            debit=Decimal('0.00'),
            credit=purchase.grand_total
        )
        
        return debit_entry, credit_entry

    @staticmethod
    def create_sale_ledger_entry(sale, company):
        """
        Create ledger entries for a sale transaction.
        
        Double-Entry Accounting:
        - Debit: Customer Receivable (Asset) = grand_total
        - Credit: Sales Account (Revenue) = grand_total
        
        Args:
            sale: Sale instance
            company: Company instance
            
        Returns:
            tuple: (debit_entry, credit_entry) Ledger instances
        """
        content_type = ContentType.objects.get_for_model(sale)
        party = sale.customer  # Customer is a proxy of Party
        
        description = f"Sales Invoice {sale.invoice_number}"
        if sale.notes:
            description += f" - {sale.notes[:100]}"
        
        # Debit: Customer Receivable Account
        debit_entry = Ledger.objects.create(
            company=company,
            party=party,
            content_type=content_type,
            object_id=sale.id,
            date=sale.invoice_date,
            txn_id=sale.invoice_number or f"SAL-{sale.id}",
            txn_type=TransactionType.SALE,
            description=f"{description} - Customer Receivable",
            debit=sale.grand_total,
            credit=Decimal('0.00')
        )
        
        # Credit: Sales Revenue Account
        credit_entry = Ledger.objects.create(
            company=company,
            party=party,
            content_type=content_type,
            object_id=sale.id,
            date=sale.invoice_date,
            txn_id=sale.invoice_number or f"SAL-{sale.id}",
            txn_type=TransactionType.SALE,
            description=f"{description} - Sales Revenue",
            debit=Decimal('0.00'),
            credit=sale.grand_total
        )
        
        return debit_entry, credit_entry

    @staticmethod
    def create_payment_ledger_entry(payment, company, party, payment_type='received'):
        """
        Create ledger entries for a payment transaction.
        
        For Payment Received (from customer):
        - Debit: Cash/Bank Account = amount
        - Credit: Customer Receivable = amount
        
        For Payment Made (to supplier):
        - Debit: Supplier Payable = amount
        - Credit: Cash/Bank Account = amount
        
        Args:
            payment: Payment instance (CustomerPayment or SupplierPayment)
            company: Company instance
            party: Party instance (Customer or Supplier)
            payment_type: 'received' or 'made'
            
        Returns:
            tuple: (debit_entry, credit_entry) Ledger instances
        """
        content_type = ContentType.objects.get_for_model(payment)
        
        description = f"Payment {payment.reference_number}"
        if hasattr(payment, 'notes') and payment.notes:
            description += f" - {payment.notes[:100]}"
        
        if payment_type == 'received':
            # Payment received from customer
            # Debit: Cash/Bank Account
            debit_entry = Ledger.objects.create(
                company=company,
                party=party,
                content_type=content_type,
                object_id=payment.id,
                date=payment.date.date() if hasattr(payment.date, 'date') else payment.date,
                txn_id=payment.reference_number,
                txn_type=TransactionType.PAYMENT_RECEIVED,
                description=f"{description} - Cash/Bank",
                debit=payment.amount,
                credit=Decimal('0.00')
            )
            
            # Credit: Customer Receivable
            credit_entry = Ledger.objects.create(
                company=company,
                party=party,
                content_type=content_type,
                object_id=payment.id,
                date=payment.date.date() if hasattr(payment.date, 'date') else payment.date,
                txn_id=payment.reference_number,
                txn_type=TransactionType.PAYMENT_RECEIVED,
                description=f"{description} - Customer Receivable",
                debit=Decimal('0.00'),
                credit=payment.amount
            )
        else:
            # Payment made to supplier
            # Debit: Supplier Payable
            debit_entry = Ledger.objects.create(
                company=company,
                party=party,
                content_type=content_type,
                object_id=payment.id,
                date=payment.date.date() if hasattr(payment.date, 'date') else payment.date,
                txn_id=payment.reference_number,
                txn_type=TransactionType.PAYMENT_MADE,
                description=f"{description} - Supplier Payable",
                debit=payment.amount,
                credit=Decimal('0.00')
            )
            
            # Credit: Cash/Bank Account
            credit_entry = Ledger.objects.create(
                company=company,
                party=party,
                content_type=content_type,
                object_id=payment.id,
                date=payment.date.date() if hasattr(payment.date, 'date') else payment.date,
                txn_id=payment.reference_number,
                txn_type=TransactionType.PAYMENT_MADE,
                description=f"{description} - Cash/Bank",
                debit=Decimal('0.00'),
                credit=payment.amount
            )
        
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
    def update_party_balance(party, company):
        """
        Calculate and update party balance from ledger entries.
        Balance = Sum of (Debits - Credits) for the party.
        
        This is typically called after ledger entries are created/updated.
        
        Args:
            party: Party instance
            company: Company instance
        """
        ledger_entries = Ledger.objects.filter(company=company, party=party)
        
        total_debit = sum(entry.debit for entry in ledger_entries)
        total_credit = sum(entry.credit for entry in ledger_entries)
        
        balance = total_debit - total_credit
        
        # Update party balance
        from core.models import Party as PartyModel
        PartyModel.objects.filter(id=party.id, company=company).update(balance=balance)
