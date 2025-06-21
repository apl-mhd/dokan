from .models import Purchase, PurchaseItem
from .serializers import PurchaseSerializer, PurchaseItemSerializer
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from supplier.models import Supplier
from product.models import Product, Unit
from django.shortcuts import get_object_or_404
from django.db import transaction
import uuid


# Create your views here.

class PurchaseAPIView(APIView):
    # permission_classes = [IsAuthenticated]  # Allow any user to access this API

    def get(self, request):
        # Here you can implement your logic to fetch purchase data

        data = {
            "message": "This is a sample response from the Purchase API."
        }
        return Response(data)

    def post(self, request):
        data = request.data

        try:
            with transaction.atomic():
                purchase_serializer = PurchaseSerializer(data={
                    "supplier": data.get("supplier"),
                    "invoice_number": str(uuid.uuid4()),
                    "invoice_date": data.get("invoice_date"),
                    "total_amount": data.get("total_amount"),
                    "status": data.get("status", "pending"),
                    "created_by": request.user.id,
                })

                if not purchase_serializer.is_valid():
                    return Response(purchase_serializer.errors, status=400)

                purchase_serializer.save()

                purchase_items = data.get("purchase_items", [])
                items = []

                total_amount = 0

                for item in purchase_items:
                    purchase_item_serializer = PurchaseItemSerializer(
                        data=item)

                    if not purchase_item_serializer.is_valid():
                        return Response(purchase_item_serializer.errors, status=400)

                    item_total_price = item['quantity'] * item['unit_price']
                    total_amount += item_total_price


                    items.append(PurchaseItem(purchase=purchase_serializer.instance,
                                              product=get_object_or_404(
                                                  Product, id=item['product']),
                                              quantity=item['quantity'],
                                              unit=get_object_or_404(
                                                  Unit, id=item['unit']),
                                              unit_price=item['unit_price'],
                                              total_price=item_total_price,
                                              ))

                PurchaseItem.objects.bulk_create(items)
                purchase_serializer.instance.total_amount = total_amount
                purchase_serializer.instance.save()

            return Response({"message": "Purchase created successfully!"}, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=500)


def test(request):
    return HttpResponse("Purchase app is working fine!")
