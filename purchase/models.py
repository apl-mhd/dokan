from django.db import models
from supplier.models import Supplier
from django.utils.timezone import now
from warehouse.models import Warehouse
from company.models import Company
from product.models import Product, Unit


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


class PurchaseReturnStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class PurchaseReturn(models.Model):
    """Model for handling returns of purchased items to suppliers"""
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.PROTECT,
        related_name='returns',
        help_text="Original purchase being returned")
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name='purchase_returns')
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='purchase_returns')
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        help_text="Warehouse from which items are being returned")
    
    return_number = models.CharField(
        max_length=128,
        unique=True,
        blank=True,
        help_text="Unique return reference number")
    return_date = models.DateField(
        default=now,
        help_text="Date of return")
    
    # Financial fields
    sub_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Total before tax and discount")
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
        default=0.00,
        help_text="Final return amount")
    
    # Refund tracking
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Amount refunded to company")
    
    # Status and tracking
    status = models.CharField(
        max_length=20,
        choices=PurchaseReturnStatus.choices,
        default=PurchaseReturnStatus.PENDING)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for return")
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes")
    
    # Audit fields
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='purchase_return_created_by')
    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='purchase_return_updated_by',
        null=True,
        blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-return_date', '-created_at']
        indexes = [
            models.Index(fields=['company', 'return_date']),
            models.Index(fields=['company', 'supplier']),
            models.Index(fields=['company', 'purchase']),
            models.Index(fields=['company', 'status']),
        ]

    def __str__(self):
        return f"Return {self.return_number or self.id} for Purchase {self.purchase.invoice_number}"


class PurchaseReturnItem(models.Model):
    """Individual items in a purchase return"""
    purchase_return = models.ForeignKey(
        PurchaseReturn,
        on_delete=models.CASCADE,
        related_name='items')
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name='purchase_return_items')
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        help_text="Product being returned")
    
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Quantity being returned")
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        help_text="Unit of measurement")
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per unit")
    line_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total for this line item")
    
    reason = models.TextField(
        blank=True,
        null=True,
        help_text="Specific reason for returning this item")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['company', 'purchase_return']),
            models.Index(fields=['company', 'product']),
        ]

    def __str__(self):
        return f"{self.product.name} ({self.quantity} {self.unit.name}) - Return {self.purchase_return.id}"

    def clean(self):
        """Validate item data"""
        from django.core.exceptions import ValidationError
        
        if self.purchase_return and self.purchase_return.company != self.company:
            raise ValidationError({
                'company': f'PurchaseReturnItem company must match PurchaseReturn company'
            })
        
        if self.quantity <= 0:
            raise ValidationError({
                'quantity': 'Return quantity must be greater than zero'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)