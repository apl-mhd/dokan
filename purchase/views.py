from .models import Purchase, PurchaseItem
from .serializers import PurchaseSerializer
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Prefetch
from purchase.services.purchase_service import create_purchase_with_items, update_purchase_with_items
from product.models import Product
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status

# Create your views here.

class PurchaseAPIView(APIView):
    # permission_classes = [IsAuthenticated]  # Allow any user to access this API

    def get(self, request):

        purchase = Purchase.objects.select_related(
            'supplier').prefetch_related(Prefetch('items', queryset=PurchaseItem.objects.select_related('product', 'unit'))).all()
        serializer = PurchaseSerializer(purchase, many=True)

        return Response({"message": "Purchasse Response", "data": serializer.data}, status=status)

    def post(self, request):
        data = request.data

        try:
            with transaction.atomic():
                purchase = create_purchase_with_items(data, request.user)
                serailizer = PurchaseSerializer(purchase)
                return Response({"message": "Purchase created successfully!", "data": serailizer.data}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def put(self, request, pk):
        data = request.data
        try:
            with transaction.atomic():

                purchase = update_purchase_with_items(pk, data, request.user)
                serializer = PurchaseSerializer(purchase)

                return Response({"message": "Purchase updated successfully!", "data": serializer.data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def delete(self, request, pk):
        try:
            purchase = get_object_or_404(Purchase, id=pk)
            purchase.delete()
            return Response({"message": "Purchase deleted successfully!"}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


def test(request):

    product = get_object_or_404(Product, id=1)
    product.update(name='update katari')

    return HttpResponse("Purchase app is working fine!")
