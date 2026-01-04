from rest_framework import serializers
from .models import Stock, StockTransaction


class StockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = Stock
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class StockTransactionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse = serializers.IntegerField(source='stock.warehouse.id', read_only=True)
    warehouse_name = serializers.CharField(source='stock.warehouse.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    reference = serializers.IntegerField(source='reference_id', read_only=True)
    notes = serializers.CharField(source='note', read_only=True)
    
    class Meta:
        model = StockTransaction
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

