from rest_framework import serializers
from .models import Stock, StockTransaction


class StockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    unit_name = serializers.SerializerMethodField()
    last_updated = serializers.DateTimeField(
        source='updated_at', read_only=True)

    class Meta:
        model = Stock
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_unit_name(self, obj):
        """Get the base unit name from the product"""
        if obj.product and obj.product.base_unit:
            return obj.product.base_unit.name
        return 'N/A'


class StockTransactionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse = serializers.IntegerField(
        source='stock.warehouse.id', read_only=True)
    warehouse_name = serializers.CharField(
        source='stock.warehouse.name', read_only=True)
    unit_name = serializers.SerializerMethodField()
    original_unit_name = serializers.CharField(
        source='unit.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    reference = serializers.IntegerField(source='reference_id', read_only=True)
    notes = serializers.CharField(source='note', read_only=True)
    reference_type = serializers.SerializerMethodField()
    reference_number = serializers.SerializerMethodField()

    class Meta:
        model = StockTransaction
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_unit_name(self, obj):
        """Get the base unit name from the product (quantities are stored in base units)"""
        if obj.product and obj.product.base_unit:
            return obj.product.base_unit.name
        return 'N/A'

    def get_reference_type(self, obj):
        if getattr(obj, 'content_type', None):
            return obj.content_type.model
        return None

    def get_reference_number(self, obj):
        ref = getattr(obj, 'content_object', None)
        if not ref:
            return None
        # Purchases/Sales usually have invoice_number; returns have return_number
        for attr in ('invoice_number', 'return_number'):
            val = getattr(ref, attr, None)
            if val:
                return val
        return f"{ref.__class__.__name__} #{getattr(ref, 'id', '')}".strip()
