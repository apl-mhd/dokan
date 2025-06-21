from django.db import models
from supplier.models import Supplier
from django.utils.timezone import now


class Purchase(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=128,unique=True, null=True, blank=True)
    invoice_date = models.DateField(default=now)
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)

    created_by = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='purchase_created_by')
    updated_by = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='purchase_updated_by', null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='pending')
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Purchase {self.id} from {self.supplier.name}"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE)
    product = models.ForeignKey('product.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit = models.ForeignKey('product.Unit', on_delete=models.CASCADE)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    # created_by = models.ForeignKey(
    #     'auth.User', on_delete=models.CASCADE, related_name='purchase_item_created_by')
    # updated_by = models.ForeignKey(
    #     'auth.User', on_delete=models.CASCADE, related_name='purchase_item_updated_by')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} in {self.purchase}"
