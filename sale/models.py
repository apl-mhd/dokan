from django.conf import settings
from django.db import models
from django.utils.timezone import now
from customer.models import Customer
from product.models import Product, Unit
from company.models import Company
from warehouse.models import Warehouse


class SaleStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    DELIVERED = 'delivered', 'Delivered'

    PARTIALLY_RETURNED = 'partial_return', 'Partially Returned'
    RETURNED = 'returned', 'Fully Returned'
    CANCELLED = 'cancelled', 'Cancelled'


class PaymentStatus(models.TextChoices):
    UNPAID = 'unpaid', 'Unpaid'
    PARTIAL = 'partial', 'Partial'
    PAID = 'paid', 'Paid'
    OVERPAID = 'overpaid', 'Overpaid'


class Sale(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name='sales')
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name='sales')
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name='sales')
    invoice_number = models.CharField(max_length=128, null=True, blank=True)
    invoice_date = models.DateField(default=now)
    sub_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    delivery_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sale_created_by')
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sale_updated_by', null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=SaleStatus.choices, default=SaleStatus.PENDING)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # def __str__(self):
    #     return f"Sale {self.id} to {self.customer.name}"


class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name='items')
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name='sale_items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=4)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # def __str__(self):
    #     return f"{self.product.name} - {self.quantity} {self.unit.name} @ {self.unit_price} each"


class SaleReturnStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class RefundStatus(models.TextChoices):
    NOT_REFUNDED = 'not_refunded', 'Not Refunded'
    PARTIAL = 'partial', 'Partial'
    REFUNDED = 'refunded', 'Refunded'


class SaleReturn(models.Model):
    """Model to track sale returns"""
    sale = models.ForeignKey(
        Sale, on_delete=models.PROTECT, related_name='returns')
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name='sale_returns')
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name='sale_returns')
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name='sale_returns')

    return_number = models.CharField(max_length=128, unique=True, blank=True)
    return_date = models.DateField(default=now)

    # Financial details
    sub_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Total before tax and discount")
    tax = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Discount on returned items")
    grand_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Total amount to be refunded")
    refunded_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Amount already refunded to customer")

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=SaleReturnStatus.choices,
        default=SaleReturnStatus.PENDING)
    refund_status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.NOT_REFUNDED)

    # Reason for return
    return_reason = models.TextField(
        help_text="Reason for returning the items")
    notes = models.TextField(null=True, blank=True)

    # Timestamps and user tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sale_return_created_by')
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sale_return_updated_by',
        null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['company', 'return_date']),
            models.Index(fields=['company', 'customer']),
            models.Index(fields=['company', 'sale']),
            models.Index(fields=['status', 'refund_status']),
        ]
        ordering = ['-return_date', '-created_at']

    def __str__(self):
        return f"Return {self.return_number} for Sale {self.sale.invoice_number}"


class SaleReturnItem(models.Model):
    """Model to track individual items in a sale return"""
    sale_return = models.ForeignKey(
        SaleReturn, on_delete=models.CASCADE, related_name='items')
    sale_item = models.ForeignKey(
        SaleItem, on_delete=models.PROTECT, related_name='return_items',
        help_text="Reference to the original sale item")
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name='sale_return_items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)

    # Quantity and pricing
    returned_quantity = models.DecimalField(
        max_digits=10, decimal_places=4,
        help_text="Quantity being returned")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Price per unit from original sale")
    line_total = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Total for this return line item")

    # Item condition
    condition = models.CharField(
        max_length=50,
        choices=[
            ('good', 'Good Condition'),
            ('damaged', 'Damaged'),
            ('defective', 'Defective'),
            ('expired', 'Expired'),
            ('wrong_item', 'Wrong Item'),
        ],
        default='good')
    condition_notes = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['company', 'sale_return']),
            models.Index(fields=['product', 'company']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.returned_quantity} {self.unit.name} @ {self.unit_price}"

    def clean(self):
        """Validate that return quantity doesn't exceed original quantity"""
        from django.core.exceptions import ValidationError

        # Validate company consistency
        if self.sale_return and self.sale_return.company != self.company:
            raise ValidationError({
                'company': f'SaleReturnItem company must match SaleReturn company ({self.sale_return.company.name})'
            })

        # Validate product matches sale item
        if self.sale_item and self.sale_item.product != self.product:
            raise ValidationError({
                'product': 'Product must match the original sale item product'
            })

        # Validate returned quantity doesn't exceed original quantity
        if self.sale_item:
            # Get total already returned for this sale item
            existing_returns = SaleReturnItem.objects.filter(
                sale_item=self.sale_item,
                sale_return__status__in=[
                    SaleReturnStatus.PENDING, SaleReturnStatus.COMPLETED]
            ).exclude(pk=self.pk)

            total_returned = sum(
                item.returned_quantity for item in existing_returns) if existing_returns else 0

            if (total_returned + self.returned_quantity) > self.sale_item.quantity:
                raise ValidationError({
                    'returned_quantity': f'Cannot return more than original quantity. '
                    f'Original: {self.sale_item.quantity}, '
                    f'Already returned: {total_returned}, '
                    f'Attempting to return: {self.returned_quantity}'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
