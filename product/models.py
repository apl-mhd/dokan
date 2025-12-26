from django.db import models

# Create your models here.


class UnitCategory(models.Model):
    name = models.CharField(max_length=50)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Unit(models.Model):
    name = models.CharField(max_length=50)
    conversion_factor = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    is_base_unit = models.BooleanField(default=False)
    unit_category = models.ForeignKey(UnitCategory, related_name="units",  on_delete=models.PROTECT, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.pk} - {self.name} - {self.unit_category.name}"


class Category(models.Model):
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    base_unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="products", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


# class Warehouse(models.Model):
#     name = models.CharField(max_length=20)
#     location = models.CharField(max_length=50)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return self.name


# class TransactionType(models.TextChoices):
#     PURCHASE = 'purchase', 'Purchase'
#     SALE = 'sale', 'Sale'
#     SALE_RETURN = 'sale_return', 'Sale Return'
#     PURCHASE_RETURN = 'purchase_return', 'Purchase Return'
#     TRANSFER_IN = 'transfer_in', 'Transfer In'
#     TRANSFER_OUT = 'transfer_out', 'Transfer Out'
#     ADJUSTMENT_IN = 'adjustment_in', 'Adjustment In'
#     ADJUSTMENT_OUT = 'adjustment_out', 'Adjustment Out'


# class Stock(models.Model):
#     product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stocks")
#     warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
#     quantity = models.DecimalField(max_digits=10, decimal_places=4)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return f"{self.product.name} - {self.quantity}"


# class StockLedger(models.Model):
#     product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_ledgers")
#     quantity = models.DecimalField(max_digits=10, decimal_places=4)
#     stock = models.ForeignKey(Stock, on_delete=models.PROTECT)
#     transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
#     reference_number = models.CharField(max_length=50)

#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)


#     def __str__(self):
#         return f"{self.product.name} - {self.quantity} - {self.transaction_type}"
