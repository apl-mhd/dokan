from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError
from inventory.models import Stock, StockTransaction, TransactionType, StockDirection
from product.models import Product, Unit
from purchase.models import Purchase, PurchaseItem
from supplier.models import Supplier
from warehouse.models import Warehouse
from purchase.serializers import PurchaseSerializer, PurchaseItemSerializer

from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from uuid import uuid4



class PurchaseService:


    @staticmethod
    def update_purchase(data, user):

        purchase = get_object_or_404(Purchase, id=data.get("id"))

        items = data.get("items")

        try:
            with transaction.atomic():
                purchase.purchase_items.all().delete()
                purchase.save()

                grand_total = Decimal('0.00')
                purchase_items = []
                for item in items:
                    product = get_object_or_404(Product, id=item['product'])
                    unit = get_object_or_404(Unit, id=item['unit'])
                    quantity = Decimal(item['quantity'])
                    unit_price = Decimal(item['unit_price'])
                    line_total = quantity * unit_price
                    grand_total += line_total

                    purchase_items.append(PurchaseItem(
                        purchase=purchase,
                        product=product,
                        quantity=quantity,
                        unit=unit,
                        unit_price=unit_price,
                        line_total=line_total,
                    ))

                PurchaseItem.objects.bulk_create(purchase_items)
                purchase.grand_total = grand_total
                purchase.save(update_fields=["grand_total"])


                return purchase
            
        except IntegrityError as e:
            raise ValidationError(str(e))
        


    @staticmethod
    def create_purchase(data, user):
        warehouse = get_object_or_404(Warehouse, id=data.get("warehouse"))
        print(data)
        supplier = get_object_or_404(Supplier, id=data.get("supplier"))
        items = data.get("items")
        grand_total = Decimal('0.00')
        purchase_items = []
        try:
            with transaction.atomic():
                purchase = Purchase.objects.create(
                    invoice_number=str(uuid4()),
                    status=data.get("status", "pending"),
                    created_by=user,
                    warehouse=warehouse,
                    supplier=supplier,
                )
                
                for item in items:
                    product = get_object_or_404(Product, id=item['product'])
                    unit = get_object_or_404(Unit, id=item['unit'])
                    quantity = Decimal(item['quantity'])
                    unit_price = Decimal(item['unit_price'])
                    line_total = quantity * unit_price
                    grand_total += line_total

                    purchase_items.append(PurchaseItem(
                        purchase=purchase,
                        product=product,
                        quantity=quantity,
                        unit=unit,
                        unit_price=unit_price,
                        line_total=line_total,
                    ))
                    
                    stock, _= Stock.objects.get_or_create(
                        product=product,
                        warehouse=warehouse,
                        defaults={
                            "quantity": quantity,
                        }
                    )
                    stock.quantity += quantity
                    stock.save(update_fields=["quantity"])

                    stock_transaction = StockTransaction(
                        product=product,
                        quantity=quantity,
                        stock=stock,
                        direction=StockDirection.IN,
                        transaction_type=TransactionType.PURCHASE,
                        reference_id=purchase.id,
                        note=f"Purchase {purchase.invoice_number}",
                    )
                    stock_transaction.save()


                PurchaseItem.objects.bulk_create(purchase_items)
                purchase.grand_total = grand_total
                purchase.save(update_fields=["grand_total"])

                return purchase
            
        except IntegrityError as e:
            raise ValidationError(str(e))

        



        


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
