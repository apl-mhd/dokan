from django.db import models
from product.models import Product
from warehouse.models import Warehouse
from company.models import Company
# Create your models here.



class TransactionType(models.TextChoices):
    PURCHASE = 'purchase', 'Purchase'
    SALE = 'sale', 'Sale'
    SALE_RETURN = 'sale_return', 'Sale Return'
    PURCHASE_RETURN = 'purchase_return', 'Purchase Return'
    TRANSFER_IN = 'transfer_in', 'Transfer In'
    TRANSFER_OUT = 'transfer_out', 'Transfer Out'
    ADJUSTMENT_IN = 'adjustment_in', 'Adjustment In'
    ADJUSTMENT_OUT = 'adjustment_out', 'Adjustment Out'

class StockDirection(models.TextChoices):
    IN = 'in', 'In'
    OUT = 'out', 'Out'


class Stock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stocks")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='stocks')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"


class StockTransaction(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_ledgers")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='stock_ledgers')
    quantity = models.DecimalField(max_digits=10, decimal_places=4)
    stock = models.ForeignKey(Stock, on_delete=models.PROTECT)
    direction = models.CharField(max_length=10, choices=StockDirection.choices)
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    reference_id = models.PositiveIntegerField()
    note = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} - {self.transaction_type}"
