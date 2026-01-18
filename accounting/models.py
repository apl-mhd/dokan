from django.db import models
from company.models import Company
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError


class TransactionType(models.TextChoices):
    OPENING_BALANCE = 'opening_balance', 'Opening Balance'
    SALE = 'sale', 'Sale (Invoice)'
    PURCHASE = 'purchase', 'Purchase'
    SALE_RETURN = 'sale_return', 'Sales Return'
    PURCHASE_RETURN = 'purchase_return', 'Purchase Return'
    PAYMENT_RECEIVED = 'payment_received', 'Payment Received'
    PAYMENT_MADE = 'payment_made', 'Payment Made'
    ADJUSTMENT = 'adjustment', 'Adjustment'


class Ledger(models.Model):
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="ledger_entries")
    party = models.ForeignKey(
        'core.Party', on_delete=models.CASCADE, related_name="ledger_entries")

    # 2. The Generic Relation (The Link to Sales/Purchases/etc.)
    # This stores the 'ID' and 'Table Name' of the source document
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    # 3. Transaction Details
    date = models.DateField(db_index=True)
    txn_id = models.CharField(
        max_length=50, db_index=True, help_text="Business ID like INV-1001")
    txn_type = models.CharField(max_length=20, choices=TransactionType.choices)
    description = models.CharField(max_length=255, blank=True)

    # 4. Financial Columns
    debit = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    credit = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    

    # 5. Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        # Index for fast report generation
        indexes = [
            models.Index(fields=['company', 'party', 'date']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.txn_id} - {self.party.name} ({self.txn_type})"

    def clean(self):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError(
                "Only one of debit or credit can be greater than zero.")
        if self.debit < 0 or self.credit < 0:
            raise ValidationError("Debit and credit must be greater than 0")

    @property
    def amount(self):
        """Returns the net impact of this row"""
        return self.debit - self.credit
