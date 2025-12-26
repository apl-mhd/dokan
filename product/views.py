from django.shortcuts import render
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UnitSerializer, ProductSerializer
from rest_framework import status
from .models import Product, Unit, UnitCategory
from decimal import Decimal
# Create your views here.



class ProductAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, product_id):

        products = Product.objects.select_related('base_unit__unit_category').prefetch_related('stocks').all()
        data = []

        for product in products:
            unit = Unit.objects.filter(unit_category=product.base_unit.unit_category)

            print(product.stocks.first().quantity)
            unit_list = [
                {
                "id": i.id,
                "name": i.name,
                "conversion_factor": str(i.conversion_factor),
                }
                for i in unit
            ]

            data.append({
                "id": product.id,
                "name": product.name,
                "base_unit": {
                    "id": product.base_unit.id,
                    "name": product.base_unit.name,
                    "conversion_factor": str(product.base_unit.conversion_factor),
                },
                "units": unit_list,
                "stocks": product.stocks.first().quantity,
            })

        return Response(data)
        


class UnitModelSerializer(viewsets.ModelViewSet):
    queryset = UnitSerializer
    serializer_class = UnitSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
   

class ProductUnitListAPIView(APIView):
    permission_classes = [permissions.AllowAny]
  
    def get(self, request, product_id):

        try:
            product = Product.objects.select_related('unit').get(id=product_id)
        except Product.DoesNotExist:
            return Response({
                'error': 'Product not found'
            }, status=status.HTTP_404_NOT_FOUND)

        unit = Unit.objects.filter(unit_category=product.unit.unit_category)

        data =[
            {"id": i.id, "name": i.name, "conversion_factor": str(i.conversion_factor), "is_base_unit": i.is_base_unit}
            
            for i in unit
            ]


        
        return Response({
            "data": data,
        })
        


class StockCheckAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id):
        product_id = request.query_params.get('product_id')
        unit_id = request.query_params.get('unit_id')
        quantity = request.query_params.get('quantity')
        warehouse_id = request.query_params.get('warehouse_id')

        if not all([product_id, unit_id, quantity, warehouse_id]):
            return Response({
                'error': 'All parameters are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        quantity = Decimal(quantity)

        unit = Unit.objects.get(id=unit_id)
        required_base_qt = quantity * unit.conversion_factor

        stock  = Stock.objects.filter(product_id=product_id, warehouse_id=warehouse_id).first()

        available_stock = stock.quantity if stock else 0


        is_available = available_stock >= required_base_qty

        return Response({
            "is_available": is_available,
            "required_quantity": str(required_base_qty),
            "available_stock": str(available_stock),
            "base_unit": unit.unit_category.base_unit.name
        })
        