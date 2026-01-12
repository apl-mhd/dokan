from rest_framework import serializers
from sale.models import Sale, SaleItem, SaleStatus
from customer.models import Customer


class SaleItemOutputSerializer(serializers.ModelSerializer):
    """Serializer for sale items in output (read-only)"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    
    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit', 'unit_name',
                  'unit_price', 'line_total', 'created_at']
        read_only_fields = ['line_total', 'created_at', 'product_name', 'unit_name']


class SaleItemInputSerializer(serializers.Serializer):
    """Serializer for sale item input (used in create/update operations)"""
    product = serializers.IntegerField(required=True)
    quantity = serializers.DecimalField(
        max_digits=10, decimal_places=4, required=True)
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


class SaleCreateInputSerializer(serializers.Serializer):
    """Serializer for creating a sale"""
    customer = serializers.IntegerField(required=True)
    warehouse = serializers.IntegerField(required=True)
    items = SaleItemInputSerializer(many=True, required=True)
    status = serializers.ChoiceField(
        choices=SaleStatus.choices,
        default=SaleStatus.PENDING,
        required=False
    )
    notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    invoice_date = serializers.DateField(required=False)

    def validate_items(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one item is required.")
        return value


class SaleUpdateInputSerializer(serializers.Serializer):
    """Serializer for updating a sale"""
    id = serializers.IntegerField(required=True)
    items = SaleItemInputSerializer(many=True, required=True)
    status = serializers.ChoiceField(
        choices=SaleStatus.choices,
        required=False
    )
    notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)

    def validate_items(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one item is required.")
        return value


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name']


class SaleItemSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(source='sale.customer', read_only=True)

    class Meta:
        model = SaleItem
        exclude = ['sale']
        read_only_fields = ['line_total', 'customer']


class SaleSerializer(serializers.ModelSerializer):
    """Serializer for sale output (read operations)"""
    items = SaleItemOutputSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(
        source='customer.name', read_only=True)
    customer_phone = serializers.CharField(
        source='customer.phone', read_only=True)
    customer_address = serializers.CharField(
        source='customer.address', read_only=True)
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = Sale
        fields = '__all__'
        read_only_fields = ['grand_total', 'company',
                            'created_by', 'created_at', 'updated_at']
