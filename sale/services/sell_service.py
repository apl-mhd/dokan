from decimal import Decimal
from django.shortcuts import get_object_or_404
from sale.models import Sale, SaleItem
from customer.models import Customer
from sale.serializers import SaleItemSerializer, SaleSerializer
from product.models import Product, Unit
from uuid import uuid4
from customer.models import Customer
from inventory.models import Stock
from django.db import transaction


def create_sell_with_items(data, user):

    items = []
    grand_total = Decimal('0.00')
    for item in data.get('items', []):
        serialzer = SaleItemSerializer(data=item)
        serialzer.is_valid(raise_exception=True)

        price = Decimal(item['unit_price'])
        quantity = Decimal(item['quantity'])
        sub_total = price * quantity
        grand_total += sub_total

        items.append(SaleItem(
            unit_price=price,
            quantity=quantity,
            unit=get_object_or_404(Unit,  id=item.get('unit')),
            product=get_object_or_404(
                Product, id=item.get('product')),
            sub_total=sub_total
        )
        )
    sale_serializer = SaleSerializer(data={
        "customer": data.get("customer"),
        "invoice_number": str(uuid4()),
        "invoice_date": data.get("invoice_date"),
        "grand_total": grand_total,
        "status": data.get("status", "pending"),
        "created_by": user.id,
    })

    sale_serializer.is_valid(raise_exception=True)
    sale = sale_serializer.save()

    for item in items:
        item.sale = sale

    SaleItem.objects.bulk_create(items)

    return sale



def create_sale_transaction(customer_id, product_id, qty, price):

    with transaction.atomic():
        customer = get_object_or_404(Customer, id=customer_id)
        product = get_object_or_404(Product, id=product_id)
        stock = get_object_or_404(Stock, product=product)

        if stock.quantity < qty:
            raise ValueError(f"Not enough stock for product {stock.quantity}")

        stock.quantity -= qty
        stock.save()

        sale_item = SaleItem.objects.create(
            product=product,
            quantity=qty,
            unit_price=price,
            sub_total=price * qty,
            sale=sale
        )
