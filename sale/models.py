from django.db import models

# Create your models here.
from django.db import models
from django.utils.timezone import now
from customer.models import Customer
from product.models import Product, Unit
from company.models import Company
from warehouse.models import Warehouse


class SaleStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    DELIVERED = 'delivered', 'Delivered'
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
        'auth.User', on_delete=models.CASCADE, related_name='sale_created_by')
    updated_by = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='sale_updated_by', null=True, blank=True)
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
