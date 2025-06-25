from rest_framework.serializers import ModelSerializer
from sale.models import Sale, SaleItem


class SaleItemSerializer(ModelSerializer):

    class Meta:
        model = SaleItem
        fields = '__all__'
        read_only_fields = ['sale', 'sub_total', 'updated_by']


class SaleSerializer(ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = '__all__'
