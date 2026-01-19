from django.utils import timezone
from rest_framework import serializers
from .models import Purchase, PurchaseItem, PurchaseStatus, PaymentStatus
from supplier.models import Supplier


def get_default_invoice_date():
    """Default function for invoice_date field"""
    return timezone.now().date()


class ItemSerializer(serializers.ModelSerializer):
    """Serializer for purchase items in output (read-only)"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)

    class Meta:
        model = PurchaseItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit',
                  'unit_name', 'unit_price', 'line_total', 'created_at']
        read_only_fields = ['line_total',
                            'created_at', 'product_name', 'unit_name']


class PurchaseItemInputSerializer(serializers.Serializer):
    """Serializer for purchase item input (used in create/update operations)"""
    product = serializers.IntegerField(required=True)
    quantity = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=True)
    unit = serializers.IntegerField(required=True)
    unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=True)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Quantity must be greater than zero.")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative.")
        return value


class PurchaseCreateInputSerializer(serializers.Serializer):
    """Serializer for creating a purchase"""
    supplier = serializers.IntegerField(required=True)
    warehouse = serializers.IntegerField(required=True)
    items = PurchaseItemInputSerializer(many=True, required=True)
    status = serializers.ChoiceField(
        choices=PurchaseStatus.choices,
        default=PurchaseStatus.PENDING,
        required=False
    )
    sub_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    tax = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    delivery_charge = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    paid_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    invoice_date = serializers.DateField(
        required=False, default=get_default_invoice_date)

    def validate_items(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one item is required.")
        return value


class PurchaseUpdateInputSerializer(serializers.Serializer):
    """Serializer for updating a purchase"""
    id = serializers.IntegerField(required=True)
    items = PurchaseItemInputSerializer(many=True, required=True)
    status = serializers.ChoiceField(
        choices=PurchaseStatus.choices,
        required=False
    )
    sub_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    tax = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    delivery_charge = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    paid_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)

    def validate_items(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one item is required.")
        return value


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name']


class PurchaseItemSerializer(serializers.ModelSerializer):
    supplier = SupplierSerializer(source='purchase.supplier', read_only=True)

    class Meta:
        model = PurchaseItem
        # fields = '__all__'
        exclude = ['purchase']
        read_only_fields = ['line_total', 'supplier']


class PurchaseSerializer(serializers.ModelSerializer):
    """Serializer for purchase output (read operations)"""
    items = ItemSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(
        source='supplier.name', read_only=True)
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = Purchase
        fields = '__all__'
        read_only_fields = ['grand_total', 'company',
                            'created_by', 'created_at', 'updated_at']

    def validate_paid_amount(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Paid amount cannot be negative.")
        return value

    def validate_discount(self, value):
        if value < 0:
            raise serializers.ValidationError("Discount cannot be negative.")
        return value

    def validate_tax(self, value):
        if value < 0:
            raise serializers.ValidationError("Tax cannot be negative.")
        return value

    def validate_delivery_charge(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Delivery charge cannot be negative.")
        return value
