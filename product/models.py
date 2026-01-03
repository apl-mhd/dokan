from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal


class UnitCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Unit Category"
        verbose_name_plural = "Unit Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_base_unit(self):
        """
        Get the base unit for this category.
        Returns the unit where is_base_unit=True for this category.

        Returns:
            Unit instance or None
        """
        return self.units.filter(is_base_unit=True).first()


class Unit(models.Model):
    name = models.CharField(max_length=50)
    conversion_factor = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('1.0000'),
        help_text="Conversion factor to base unit (e.g., 1 kg = 1000 g, so for gram conversion_factor=0.001)"
    )
    is_base_unit = models.BooleanField(
        default=False,
        help_text="Whether this is the base unit for the category"
    )
    unit_category = models.ForeignKey(
        UnitCategory,
        related_name="units",
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['unit_category', 'name']
        verbose_name = "Unit"
        verbose_name_plural = "Units"

    def __str__(self):
        category_name = self.unit_category.name if self.unit_category else "No Category"
        return f"{self.name} ({category_name})"

    def clean(self):
        if self.is_base_unit and self.conversion_factor != Decimal('1.0000'):
            raise ValidationError({
                'conversion_factor': 'Base unit must have conversion_factor = 1.0000'
            })

        if self.unit_category:
            # Check if there's already a base unit for this category
            existing_base = Unit.objects.filter(
                unit_category=self.unit_category,
                is_base_unit=True
            ).exclude(pk=self.pk).first()

            if self.is_base_unit and existing_base:
                raise ValidationError({
                    'is_base_unit': f'Category already has a base unit: {existing_base.name}'
                })

    def convert_to_base_unit(self, quantity):
        """
        Convert quantity from this unit to base unit.

        Args:
            quantity: Decimal quantity in this unit

        Returns:
            Decimal quantity in base unit
        """
        return quantity * self.conversion_factor

    def convert_from_base_unit(self, quantity):
        """
        Convert quantity from base unit to this unit.

        Args:
            quantity: Decimal quantity in base unit

        Returns:
            Decimal quantity in this unit
        """
        if self.conversion_factor == 0:
            return Decimal('0.00')
        return quantity / self.conversion_factor


class Category(models.Model):
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products"
    )
    base_unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
        help_text="Base unit for stock tracking. Stock quantities are stored in this unit."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def __str__(self):
        return self.name

    def clean(self):
        if self.base_unit and self.base_unit.unit_category:
            # Ensure base_unit is actually a base unit
            if not self.base_unit.is_base_unit:
                raise ValidationError({
                    'base_unit': 'Product base_unit must be a base unit (is_base_unit=True).'
                })


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
