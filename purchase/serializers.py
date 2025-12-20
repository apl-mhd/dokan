from rest_framework import serializers
from decimal import Decimal
from .models import Purchase, PurchaseItem
from supplier.models import Supplier



class ItemSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = PurchaseItem
        fields = ['product', 'quantity', 'unit', 'unit_price', 'line_total']
        extra_kwargs = {
            'unit_price': {'required': True},
            'line_total': {'required': True},
        }

    def validate_product(self, attrs):
        raise serializers.ValidationError("error")

class PurchaseCreateSerializer(serializers.ModelSerializer):
    items = ItemSerializer(many=True, required=False) 
    class Meta:
        model = Purchase
        fields = ['supplier', 'invoice_date', 'status', 'grand_total', 'notes', "items"]

        extra_kwargs = {
            'grand_total': {'required': True},
        }



class PurchaseItemCreatSerializer(serializers.Serializer):

    purchase = PurchaseCreateSerializer()
    items = ItemSerializer(many=True)


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
    items = ItemSerializer(many=True)

    class Meta:
        model = Purchase
        fields = '__all__'
        read_only_fields = ['grand_total',
                            'created_by', 'created_at', 'updated_at']


# class PurchaseItemSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = PurchaseItem
#         fields = '__all__'
#         exclude = ['purchase']
#         read_only_fields = ['line_total']


# class PurchaseSerializer(serializers.ModelSerializer):
#     items = PurchaseItemSerializer(many=True, read_only=True)

#     class Meta:
#         model = Purchase
#         fields = '__all__'
#         # exclude = ['items']
#         read_only_fields = ['grand_total',
#                             'created_by', 'created_at', 'updated_at']

#     def create(self, validated_data):
#         purchase_items_data = validated_data.pop('items', [])
#         grand_total = Decimal('0.00')
#         user = self.context['request'].user
#         print(user)
#         # user = self.context.get('request').user
#         # print(self.context.get('request'))
#         # print(self.context)

#         items = []
#         for item in purchase_items_data:
#             quantity = Decimal(item.get('quantity', 0))
#             price = Decimal(item.get('price', 0))
#             line_total = quantity * price
#             grand_total += line_total

#             items.append(PurchaseItem(
#                 product=item.get('product'),
#                 quantity=quantity,
#                 unit_price=price,
#                 unit=item.get('unit'),
#                 line_total=quantity * price
#             ))
#         validated_data['grand_total'] = grand_total

#         purchase = Purchase.objects.create(
#             **validated_data, created_by=user)

#         for item in items:
#             item.purchase = purchase
#         PurchaseItem.objects.bulk_create(items)

#         return purchase
