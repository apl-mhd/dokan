from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from customer.models import Customer
from supplier.models import Supplier
from company.models import Company


class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Cash'
    BANK = 'bank', 'Bank Transfer'
    BKASH = 'bkash', 'bKash'
    NAGAD = 'nagad', 'Nagad'
    ROCKET = 'rocket', 'Rocket'
    UPAY = 'upay', 'Upay'
    CHEQUE = 'cheque', 'Cheque'
    CARD = 'card', 'Card'
    OTHERS = 'others', 'Others'


class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class PaymentType(models.TextChoices):
    RECEIVED = 'received', 'Received (from Customer)'
    MADE = 'made', 'Made (to Supplier)'


class Payment(models.Model):
    """Unified payment model for both customer and supplier payments"""

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name='payments')

    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        help_text="Type of payment: received from customer or made to supplier")

    # Party relationships (one will be null based on payment_type)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='customer_payments',
        null=True,
        blank=True,
        help_text="Customer (for received payments)")

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='supplier_payments',
        null=True,
        blank=True,
        help_text="Supplier (for made payments)")

    # Optional links to invoices
    sale = models.ForeignKey(
        'sale.Sale',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        help_text="Optional: Link to specific sale")

    purchase = models.ForeignKey(
        'purchase.Purchase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        help_text="Optional: Link to specific purchase")

    payment_method = models.CharField(
        max_length=50,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH)

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Payment amount")

    date = models.DateField(
        default=timezone.now,
        help_text="Payment date")

    reference_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Transaction ID, Cheque number, or Bank reference")

    # Bank/MFS specific fields
    account_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Bank account or Mobile number for MFS")

    account_holder_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Account holder or MFS account name")

    bank_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Bank name for bank transfers")

    branch_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Bank branch name")

    # Status and notes
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.COMPLETED)

    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional payment notes")

    # Audit fields
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='payment_created_by')

    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='payment_updated_by',
        null=True,
        blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['company', 'payment_type', 'date']),
            models.Index(fields=['company', 'customer', 'date']),
            models.Index(fields=['company', 'supplier', 'date']),
            models.Index(fields=['company', 'payment_method']),
            models.Index(fields=['company', 'status']),
        ]
        ordering = ['-date', '-created_at']

    def __str__(self):
        if self.payment_type == PaymentType.RECEIVED:
            party = self.customer.name if self.customer else 'Unknown'
            return f"Payment from {party} - {self.amount} ({self.payment_method})"
        else:
            party = self.supplier.name if self.supplier else 'Unknown'
            return f"Payment to {party} - {self.amount} ({self.payment_method})"

    def clean(self):
        """Validate payment data"""
        # Validate payment method specific fields
        if self.payment_method == PaymentMethod.BANK:
            if not self.bank_name:
                raise ValidationError({
                    'bank_name': 'Bank name is required for bank transfers'
                })

        if self.payment_method in [PaymentMethod.BKASH, PaymentMethod.NAGAD,
                                   PaymentMethod.ROCKET, PaymentMethod.UPAY]:
            if not self.account_number:
                raise ValidationError({
                    'account_number': 'Mobile number is required for MFS payments'
                })

        # Validate party relationships based on payment type
        if self.payment_type == PaymentType.RECEIVED:
            if not self.customer:
                raise ValidationError({
                    'customer': 'Customer is required for received payments'
                })
            if self.supplier:
                raise ValidationError({
                    'supplier': 'Supplier should not be set for received payments'
                })
            if self.customer and self.customer.company != self.company:
                raise ValidationError({
                    'customer': f'Customer must belong to company {self.company.name}'
                })
            if self.sale and self.sale.company != self.company:
                raise ValidationError({
                    'sale': f'Sale must belong to company {self.company.name}'
                })

        elif self.payment_type == PaymentType.MADE:
            if not self.supplier:
                raise ValidationError({
                    'supplier': 'Supplier is required for made payments'
                })
            if self.customer:
                raise ValidationError({
                    'customer': 'Customer should not be set for made payments'
                })
            if self.supplier and self.supplier.company != self.company:
                raise ValidationError({
                    'supplier': f'Supplier must belong to company {self.company.name}'
                })
            if self.purchase and self.purchase.company != self.company:
                raise ValidationError({
                    'purchase': f'Purchase must belong to company {self.company.name}'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_party(self):
        """Get the party (customer or supplier) for this payment"""
        return self.customer if self.payment_type == PaymentType.RECEIVED else self.supplier

    def get_party_name(self):
        """Get the party name"""
        party = self.get_party()
        return party.name if party else 'Unknown'
