from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from payment.models import Payment, PaymentType, PaymentMethod, PaymentStatus as PayStatus
from sale.models import Sale, SaleReturn, SaleReturnStatus
from purchase.models import Purchase, PurchaseReturn, PurchaseReturnStatus
from accounting.services.ledger_service import LedgerService


class PaymentFIFOService:
    """
    FIFO (First In First Out) payment service for invoices.
    Applies payments to invoices in chronological order (oldest first).
    """

    @staticmethod
    def _calculate_invoice_returns(invoice, invoice_type='sale'):
        """
        Calculate total return amount for an invoice.
        
        Args:
            invoice: Sale or Purchase instance
            invoice_type: 'sale' or 'purchase'
            
        Returns:
            Decimal: Total return amount
        """
        if invoice_type == 'sale':
            # Get all completed sale returns for this sale
            returns = SaleReturn.objects.filter(
                sale=invoice,
                status=SaleReturnStatus.COMPLETED
            )
            total_return = returns.aggregate(
                total=Sum('grand_total')
            )['total'] or Decimal('0.00')
        else:  # purchase
            # Get all completed purchase returns for this purchase
            returns = PurchaseReturn.objects.filter(
                purchase=invoice,
                status=PurchaseReturnStatus.COMPLETED
            )
            total_return = returns.aggregate(
                total=Sum('grand_total')
            )['total'] or Decimal('0.00')
        
        return total_return

    @staticmethod
    def _calculate_cash_payments(invoice, invoice_type='sale'):
        """
        Calculate total cash payments for an invoice.
        
        Args:
            invoice: Sale or Purchase instance
            invoice_type: 'sale' or 'purchase'
            
        Returns:
            Decimal: Total cash payment amount
        """
        if invoice_type == 'sale':
            payments = Payment.objects.filter(
                sale=invoice,
                payment_method=PaymentMethod.CASH,
                status=PayStatus.COMPLETED
            )
        else:  # purchase
            payments = Payment.objects.filter(
                purchase=invoice,
                payment_method=PaymentMethod.CASH,
                status=PayStatus.COMPLETED
            )
        
        total_payment = payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        return total_payment

    @staticmethod
    def _calculate_invoice_status(invoice, invoice_type='sale'):
        """
        Calculate invoice payment status using the formula:
        Status = (Invoice Total) - (Returns) - (Cash Payments)
        
        Args:
            invoice: Sale or Purchase instance
            invoice_type: 'sale' or 'purchase'
            
        Returns:
            Decimal: Remaining balance (Status)
        """
        invoice_total = invoice.grand_total or Decimal('0.00')
        returns = PaymentFIFOService._calculate_invoice_returns(invoice, invoice_type)
        cash_payments = PaymentFIFOService._calculate_cash_payments(invoice, invoice_type)
        
        status = invoice_total - returns - cash_payments
        return status

    @staticmethod
    def _get_payment_status_from_balance(balance, grand_total):
        """
        Determine payment status based on balance.
        
        Args:
            balance: Remaining balance (Status)
            grand_total: Invoice grand total
            
        Returns:
            str: Payment status ('unpaid', 'partial', 'paid', 'overpaid')
        """
        if balance <= 0:
            if balance < 0:
                return 'overpaid'
            else:
                return 'paid'
        elif balance >= grand_total:
            return 'unpaid'
        else:
            return 'partial'

    @staticmethod
    def _update_invoice_payment_status(invoice, invoice_type='sale'):
        """
        Update invoice payment status based on FIFO calculation.
        
        Args:
            invoice: Sale or Purchase instance
            invoice_type: 'sale' or 'purchase'
        """
        balance = PaymentFIFOService._calculate_invoice_status(invoice, invoice_type)
        payment_status = PaymentFIFOService._get_payment_status_from_balance(
            balance, invoice.grand_total
        )
        
        # Update invoice
        invoice.payment_status = payment_status
        invoice.save(update_fields=['payment_status'])

    @staticmethod
    def _get_unpaid_invoices(party, invoice_type='sale', company=None):
        """
        Get unpaid invoices for a party in FIFO order (oldest first).
        
        Args:
            party: Customer or Supplier instance
            invoice_type: 'sale' or 'purchase'
            company: Company instance
            
        Returns:
            QuerySet: Unpaid invoices ordered by invoice_date, created_at
        """
        if invoice_type == 'sale':
            invoices = Sale.objects.filter(
                customer=party,
                company=company,
                status='delivered'  # Only consider delivered sales
            ).order_by('invoice_date', 'created_at')
        else:  # purchase
            invoices = Purchase.objects.filter(
                supplier=party,
                company=company,
                status='completed'  # Only consider completed purchases
            ).order_by('invoice_date', 'created_at')
        
        # Filter to only unpaid/partial invoices
        unpaid_invoices = []
        for invoice in invoices:
            balance = PaymentFIFOService._calculate_invoice_status(invoice, invoice_type)
            if balance > 0:
                unpaid_invoices.append((invoice, balance))
        
        return unpaid_invoices

    @staticmethod
    @transaction.atomic
    def apply_payment_to_invoices(
        payment_amount,
        party,
        invoice_type='sale',
        company=None,
        user=None,
        specific_invoice=None,
        payment_date=None
    ):
        """
        Apply payment to invoices using FIFO logic.
        
        Args:
            payment_amount: Amount to apply
            party: Customer or Supplier instance
            invoice_type: 'sale' or 'purchase'
            company: Company instance
            user: User instance
            specific_invoice: Optional specific invoice to apply payment to first
            
        Returns:
            list: List of tuples (invoice, applied_amount) for each invoice
        """
        if payment_amount <= 0:
            raise ValidationError("Payment amount must be greater than zero")
        
        remaining_amount = payment_amount
        applied_payments = []
        
        # If specific invoice is provided, apply to it first
        if specific_invoice:
            balance = PaymentFIFOService._calculate_invoice_status(
                specific_invoice, invoice_type
            )
            if balance > 0:
                apply_amount = min(remaining_amount, balance)
                applied_payments.append((specific_invoice, apply_amount))
                remaining_amount -= apply_amount
        
        # Apply remaining amount to other unpaid invoices in FIFO order
        if remaining_amount > 0:
            unpaid_invoices = PaymentFIFOService._get_unpaid_invoices(
                party, invoice_type, company
            )
            
            # Skip the specific invoice if it was already processed
            if specific_invoice:
                unpaid_invoices = [
                    (inv, bal) for inv, bal in unpaid_invoices
                    if inv.id != specific_invoice.id
                ]
            
            for invoice, balance in unpaid_invoices:
                if remaining_amount <= 0:
                    break
                
                apply_amount = min(remaining_amount, balance)
                applied_payments.append((invoice, apply_amount))
                remaining_amount -= apply_amount
        
        # Create payment records and update invoices
        if payment_date is None:
            payment_date = timezone.now().date()
        
        for invoice, applied_amount in applied_payments:
            # Create payment record
            if invoice_type == 'sale':
                ref = f"CASH-SALE-{invoice.invoice_number or invoice.id}-{int(timezone.now().timestamp())}"
                payment = Payment.objects.create(
                    company=company,
                    payment_type=PaymentType.RECEIVED,
                    customer=party,
                    supplier=None,
                    sale=invoice,
                    purchase=None,
                    payment_method=PaymentMethod.CASH,
                    amount=applied_amount,
                    date=payment_date,
                    reference_number=ref,
                    status=PayStatus.COMPLETED,
                    notes=f"FIFO payment applied to invoice {invoice.invoice_number or invoice.id}",
                    created_by=user
                )
            else:  # purchase
                ref = f"CASH-PURCHASE-{invoice.invoice_number or invoice.id}-{int(timezone.now().timestamp())}"
                payment = Payment.objects.create(
                    company=company,
                    payment_type=PaymentType.MADE,
                    customer=None,
                    supplier=party,
                    sale=None,
                    purchase=invoice,
                    payment_method=PaymentMethod.CASH,
                    amount=applied_amount,
                    date=payment_date,
                    reference_number=ref,
                    status=PayStatus.COMPLETED,
                    notes=f"FIFO payment applied to invoice {invoice.invoice_number or invoice.id}",
                    created_by=user
                )
            
            # Create ledger entry
            payment_type_str = 'received' if invoice_type == 'sale' else 'made'
            LedgerService.create_payment_ledger_entry(
                payment, company, party, payment_type=payment_type_str, source_object=invoice
            )
            
            # Update invoice paid_amount (for backward compatibility)
            # Calculate total cash payments for this invoice
            total_cash_payments = PaymentFIFOService._calculate_cash_payments(invoice, invoice_type)
            if invoice_type == 'sale':
                invoice.paid_amount = total_cash_payments
            else:
                invoice.paid_amount = total_cash_payments
            invoice.save(update_fields=['paid_amount'])
            
            # Update invoice payment status using FIFO formula
            PaymentFIFOService._update_invoice_payment_status(invoice, invoice_type)
        
        # Update party balance
        LedgerService.update_party_balance(party, company)
        
        return applied_payments
