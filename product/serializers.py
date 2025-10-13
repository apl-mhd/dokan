from product.models import Product, Unit
from rest_framework import serializers

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'


class UnitSerializer(serializers.ModelSerializer):

    class Meta:
        model = Unit
        fields = '__all__'
        