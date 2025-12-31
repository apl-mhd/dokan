from rest_framework import serializers
from .models import Purchase, PurchaseItem, PurchaseStatus
from supplier.models import Supplier


class ItemSerializer(serializers.ModelSerializer):
    """Serializer for purchase items in output (read-only)"""
    class Meta:
        model = PurchaseItem
        fields = ['product', 'quantity', 'unit', 'unit_price', 'line_total']
        read_only_fields = ['line_total']


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
    notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    invoice_date = serializers.DateField(required=False)

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

    class Meta:
        model = Purchase
        fields = '__all__'
        read_only_fields = ['grand_total',
                            'created_by', 'created_at', 'updated_at']
