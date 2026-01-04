from rest_framework import serializers
from .models import Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = Warehouse
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

