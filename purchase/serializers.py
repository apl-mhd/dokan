from rest_framework import serializers

from .models import Purchase, PurchaseItem


class PurchaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Purchase
        fields = '__all__'


class PurchaseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseItem
        # fields = '__all__'
        exclude = ['purchase']

    # def create(self, validated_data):
    #     purchase_item = PurchaseItem.objects.create(**validated_data)
    #     return purchase_item

    # def update(self, instance, validated_data):
    #         instance.quantity = validated_data.get('quantity', instance.quantity)
    #         instance.unit_price = validated_data.get('unit_price', instance.unit_price)
    #         instance.save()
    #     return instance  