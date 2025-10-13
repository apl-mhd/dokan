from .services.sell_service import create_sell_with_items
from customer.models import Customer
from django.shortcuts import render
from django.db import transaction
from django.db.models import (Sum, Avg, Count, F, Case,
                               When, Value, IntegerField, 
                               CharField, OuterRef, Subquery)
from decimal import Decimal
from django.shortcuts import get_object_or_404
from product.models import Product, Unit
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from sale.models import Sale, SaleItem
from sale.serializers import SaleItemSerializer, SaleSerializer
from product.serializers import ProductSerializer
from uuid import uuid4

# Create your views here.


class SaleListAPIView(ListAPIView):

    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [AllowAny]



class SaleAPIView(APIView):
    # permission_classes = [IsAuthenticated]  # Allow any user to access this API

    # def get(self, request):
    #     a = Sale.objects.all()
    #     serializer = SaleSerializer(a, many=True)
    #     return Response(serializer.data)

    def get(self, request, pk):

        if pk is None:
            sales = Sale.objects.all()
            serializer = SaleSerializer(sales, many=True)
            return Response(serializer.data)
        

        else:
            sales = Sale.objects.select_related('customer').annotate(
                a = F('items__quantity') * F('items__unit_price')
            )

            for sale in sales:
                print(f"{sale.id} - {sale.customer.name}  -{sale.a}")

            # print(sales)
            

            # for sale in sales:
            #     print(sale.customer.name, sale.invoice_number, sale.grand_total)

            # print(sales)



            # for i in sales:
            #     print(i.customer.name, i.invoice_number, i.grand_total)

          

            # for customer in customers:
            #     print(customer.id, customer)

          
            
            return Response({"error": "Sale not found"}, status=status.HTTP_404_NOT_FOUND)
    
        
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
