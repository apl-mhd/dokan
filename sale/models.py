from django.db import models

# Create your models here.
from django.db import models
from django.utils.timezone import now
from customer.models import Customer
from product.models import Product, Unit


class Sale(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='sales')
    invoice_number = models.CharField(max_length=128, null=True, blank=True)
    invoice_date = models.DateField(default=now)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    created_by = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='sale_created_by')
    updated_by = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='sale_updated_by', null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ], default='pending')
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Purchase {self.id} from {self.customer.name}"


class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    sub_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} {self.unit.name} @ {self.unit_price} each"
