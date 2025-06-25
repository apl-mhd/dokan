from decimal import Decimal
from django.shortcuts import get_object_or_404
from purchase.models import Purchase, PurchaseItem
from product.models import Product, Unit
from purchase.serializers import PurchaseSerializer, PurchaseItemSerializer
from uuid import uuid4


def create_purchase_with_items(data, user):
    purchase_items = data.get("purchase_items", [])
    items = []
    grand_total = Decimal(0.00)

    for item in purchase_items:
        serializer = PurchaseItemSerializer(data=item)
        serializer.is_valid(raise_exception=True)

        quantity = Decimal(item['quantity'])
        unit_price = Decimal(item['unit_price'])
        line_total = quantity * unit_price
        grand_total += line_total

        items.append(PurchaseItem(
            product=get_object_or_404(Product, id=item['product']),
            quantity=quantity,
            unit=get_object_or_404(Unit, id=item['unit']),
            unit_price=unit_price,
            line_total=line_total,
        ))

    purchase_serializer = PurchaseSerializer(data={
        "supplier": data.get("supplier"),
        "invoice_number": str(uuid4()),
        "invoice_date": data.get("invoice_date"),
        "grand_total": grand_total,
        "status": data.get("status", "pending"),

    })

    purchase_serializer.is_valid(raise_exception=True)
    purchase = purchase_serializer.save(created_by=user)

    for item in items:
        item.purchase = purchase
    PurchaseItem.objects.bulk_create(items)

    return purchase


def update_purchase_with_items(purchase_id, data, user):
    purchase = get_object_or_404(Purchase, pk=purchase_id)
    purchase.items.all().delete()  # Clear existing items

    purchase.items.all().delete()  # Clear existing items

    # Update items
    items = []
    grand_total = Decimal('0.00')

    for item in data.get('purchase_items', []):
        serializer = PurchaseItemSerializer(data=item)
        serializer.is_valid(raise_exception=True)

        quantity = Decimal(item.get('quantity', 0))
        unit_price = Decimal(item.get('unit_price', 0))
        line_total = quantity * unit_price
        grand_total += line_total

        items.append(PurchaseItem(
            purchase=purchase,
            product=get_object_or_404(
                Product, id=item.get('product')),
            unit=get_object_or_404(
                Unit, id=item.get('unit')),
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,

        ))

    purchase_serializer = PurchaseSerializer(
        purchase, data=data, partial=True)

    purchase_serializer.is_valid(raise_exception=True)
    update_serializer = purchase_serializer.save(
        updated_by=user,
        grand_total=grand_total
    )

    PurchaseItem.objects.bulk_create(items)

    return update_serializer
