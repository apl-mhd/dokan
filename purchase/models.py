from django.db import models
from supplier.models import Supplier
from django.utils.timezone import now
from warehouse.models import Warehouse
from company.models import Company


class PurchaseStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class PaymentStatus(models.TextChoices):
    UNPAID = 'unpaid', 'Unpaid'
    PARTIAL = 'partial', 'Partial'
    PAID = 'paid', 'Paid'
    OVERPAID = 'overpaid', 'Overpaid'


class Purchase(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name='purchases')
    invoice_number = models.CharField(max_length=128, unique=True, blank=True)
    invoice_date = models.DateField(default=now)
    sub_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00)
    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00)
    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00)
    grand_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00)
    delivery_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00)
    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00)
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='purchase_created_by')
    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='purchase_updated_by',
        null=True,
        blank=True)
    status = models.CharField(
        max_length=20,
        choices=PurchaseStatus.choices,
        default=PurchaseStatus.PENDING)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Purchase {self.id} from {self.supplier.name}- {self.grand_total} - {self.invoice_number}"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name='items')
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name='purchase_items')
    product = models.ForeignKey('product.Product', on_delete=models.PROTECT)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    unit = models.ForeignKey('product.Unit', on_delete=models.PROTECT)
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    line_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['company', 'purchase']),
        ]

    def __str__(self):
        return f"{self.product.name} in {self.purchase}"

    def clean(self):
        """Validate that purchase and company are consistent"""
        from django.core.exceptions import ValidationError
        if self.purchase and self.purchase.company != self.company:
            raise ValidationError({
                'company': f'PurchaseItem company must match Purchase company ({self.purchase.company.name})'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)