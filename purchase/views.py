from .models import Purchase, PurchaseItem
from .serializers import PurchaseSerializer, PurchaseItemSerializer
from purchase.services.purchase_service import create_purchase_with_items, update_purchase_with_items
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from supplier.models import Supplier
from product.models import Product, Unit
from django.shortcuts import get_object_or_404
from django.db import transaction
from decimal import Decimal
import uuid
from django.db.models import Prefetch


# Create your views here.

class PurchaseAPIView(APIView):
    # permission_classes = [IsAuthenticated]  # Allow any user to access this API

    def get(self, request):

        purchase = Purchase.objects.select_related(
            'supplier').prefetch_related(Prefetch('items', queryset=PurchaseItem.objects.select_related('product', 'unit'))).all()
        serializer = PurchaseSerializer(purchase, many=True)

        return Response({"message": "Purchasse Response", "data": serializer.data}, status=200)

    def post(self, request):
        data = request.data

        try:
            with transaction.atomic():
                purchase = create_purchase_with_items(data, request.user)
                serailizer = PurchaseSerializer(purchase)
                return Response({"message": "Purchase created successfully!", "data": serailizer.data}, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def put(self, request, pk):
        data = request.data
        try:
            with transaction.atomic():

                purchase = update_purchase_with_items(pk, data, request.user)
                serializer = PurchaseSerializer(purchase)

                return Response({"message": "Purchase updated successfully!", "data": serializer.data}, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def delete(self, request, pk):
        try:
            purchase = get_object_or_404(Purchase, id=pk)
            purchase.delete()
            return Response({"message": "Purchase deleted successfully!"}, status=204)

        except Exception as e:
            return Response({"error": str(e)}, status=500)


def test(request):

    product = get_object_or_404(Product, id=1)
    product.update(name='update katari')

    return HttpResponse("Purchase app is working fine!")
