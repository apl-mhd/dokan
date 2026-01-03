from django.db import models
from django.core.exceptions import ValidationError
from product.models import Product
from warehouse.models import Warehouse
from company.models import Company
from product.models import Unit


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
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="stocks")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="stocks")
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="stocks")
    quantity = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'warehouse', 'company')
        indexes = [
            models.Index(fields=['company', 'product', 'warehouse']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.warehouse.name} - {self.quantity}"

    def clean(self):
        """Validate that product, warehouse, and company are consistent"""
        if self.warehouse and self.warehouse.company != self.company:
            raise ValidationError({
                'warehouse': f'Warehouse must belong to company {self.company.name}'
            })


class StockTransaction(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="stock_transactions")
    stock = models.ForeignKey(
        Stock, on_delete=models.PROTECT, related_name="transactions")
    unit = models.ForeignKey(
        Unit, on_delete=models.PROTECT, related_name="stock_transactions")
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="stock_transactions")
    quantity = models.DecimalField(max_digits=10, decimal_places=4)
    direction = models.CharField(max_length=10, choices=StockDirection.choices)
    balance_after = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Stock balance after this transaction"
    )
    transaction_type = models.CharField(
        max_length=30, choices=TransactionType.choices)
    reference_id = models.PositiveIntegerField()
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['company', 'transaction_type', 'created_at']),
            models.Index(fields=['company', 'product']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.quantity} - {self.transaction_type}"

    def clean(self):
        """Validate that stock and company are consistent"""
        if self.stock and self.stock.company != self.company:
            raise ValidationError({
                'stock': f'Stock must belong to company {self.company.name}'
            })
