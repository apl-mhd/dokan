from rest_framework import serializers
from .models import Supplier


class SupplierSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = Supplier
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'balance', 'company']
