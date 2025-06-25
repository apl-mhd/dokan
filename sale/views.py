from .services.sell_service import create_sell_with_items
from customer.models import Customer
from django.shortcuts import render
from django.db import transaction
from decimal import Decimal
from django.shortcuts import get_object_or_404
from product.models import Product, Unit
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from sale.models import Sale, SaleItem
from sale.serializers import SaleItemSerializer, SaleSerializer
from uuid import uuid4

# Create your views here.


class SaleAPIView(APIView):
    # permission_classes = [IsAuthenticated]  # Allow any user to access this API

    def get(self, request):

        return Response({"message": "Sale created successfully!"})

    def post(self, request):
        try:
            with transaction.atomic():

                sale = create_sell_with_items(request.data, request.user)
                serializer = SaleSerializer(sale)

                return Response({"message": "Sale created successfully!", "data": serializer.data}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        return render(request, 'sale/sale.html')

    def delete(self, request, pk):
        return render(request, 'sale/sale.html')
