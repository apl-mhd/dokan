from product.models import Product, Unit, UnitCategory
from rest_framework import serializers


class UnitCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitCategory
        fields = '__all__'


    class Meta:
        model = Product
        fields = '__all__'


class UnitSerializer(serializers.ModelSerializer):

    class Meta:
        model = Unit
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'
        