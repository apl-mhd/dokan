from django.shortcuts import render
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import (
    UnitSerializer,
    ProductSerializer,
    UnitCategorySerializer,
    ProductCreateInputSerializer,
    ProductUpdateInputSerializer,
    UnitCreateInputSerializer,
    UnitUpdateInputSerializer,
    UnitCategoryCreateInputSerializer,
    UnitCategoryUpdateInputSerializer
)
from rest_framework import status
from rest_framework.exceptions import ValidationError
from .models import Product, Unit, UnitCategory
from .services.product_service import ProductService, UnitService, UnitCategoryService
from inventory.models import Stock
from decimal import Decimal


class ProductAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id=None):
        """
        Get a single product by ID or list all products with units and stocks
        Company-filtered: only shows products belonging to user's company
        """
        # Check for company context (optional for now, but recommended)
        company = getattr(request, 'company', None)

        if product_id is not None:
            try:
                product = ProductService.get_product(product_id, company)
                serializer = ProductSerializer(product)
                return Response({
                    "message": "Product retrieved successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    "error": "Product not found",
                    "details": str(e)
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            products = ProductService.get_all_products(company)
            data = []

            for product in products:
                units = []
                if product.base_unit and product.base_unit.unit_category:
                    units = UnitService.get_all_units(company).filter(
                        unit_category=product.base_unit.unit_category
                    )

                unit_list = [
                    {
                        "id": unit.id,
                        "name": unit.name,
                        "conversion_factor": str(unit.conversion_factor),
                        "is_base_unit": unit.is_base_unit,
                    }
                    for unit in units
                ]

                # Get stock quantity (sum of all warehouse stocks)
                stocks = product.stocks.all()
                if company:
                    stocks = stocks.filter(company=company)
                total_stock = sum(
                    stock.quantity for stock in stocks) if stocks else Decimal('0.00')

                product_data = {
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "category": {
                        "id": product.category.id,
                        "name": product.category.name,
                    },
                    "category_name": product.category.name,
                    "base_unit": {
                        "id": product.base_unit.id,
                        "name": product.base_unit.name,
                        "conversion_factor": str(product.base_unit.conversion_factor),
                    } if product.base_unit else None,
                    "base_unit_name": product.base_unit.name if product.base_unit else None,
                    "units": unit_list,
                    "total_stock": str(total_stock),
                }
                data.append(product_data)

            return Response({
                "message": "Products retrieved successfully",
                "data": data
            }, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Create a new product
        Company-aware: automatically sets company from request context
        """
        company = getattr(request, 'company', None)
        if not company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = ProductCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            product = ProductService.create_product(
                serializer.validated_data, company)
            response_serializer = ProductSerializer(product)
            return Response({
                "message": "Product created successfully",
                "data": response_serializer.data
            }, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({
                "error": "Validation error",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "error": "Error creating product",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, product_id):
        """
        Update an existing product
        Company-aware: can only update products belonging to user's company
        """
        company = getattr(request, 'company', None)
        if not company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = ProductUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            product = ProductService.update_product(
                product_id, serializer.validated_data, company)
            response_serializer = ProductSerializer(product)
            return Response({
                "message": "Product updated successfully",
                "data": response_serializer.data
            }, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({
                "error": "Validation error",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "error": "Error updating product",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, product_id):
        """
        Delete a product
        Company-aware: can only delete products belonging to user's company
        """
        company = getattr(request, 'company', None)
        if not company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            ProductService.delete_product(product_id, company)
            return Response({
                "message": "Product deleted successfully"
            }, status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            return Response({
                "error": "Error deleting product",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]


class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [permissions.AllowAny]


class ProductUnitListAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id):
        """
        Get all units available for a product based on its base unit category
        """
        try:
            units = ProductService.get_product_units(product_id)
            data = [
                {
                    "id": unit.id,
                    "name": unit.name,
                    "conversion_factor": str(unit.conversion_factor),
                    "is_base_unit": unit.is_base_unit
                }
                for unit in units
            ]

            return Response({
                "message": "Product units retrieved successfully",
                "data": data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "error": "Product not found",
                "details": str(e)
            }, status=status.HTTP_404_NOT_FOUND)


class StockCheckAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """
        Check stock availability for a product in a specific unit and warehouse
        Query params: product_id, unit_id, quantity, warehouse_id
        """
        product_id = request.query_params.get('product_id')
        unit_id = request.query_params.get('unit_id')
        quantity = request.query_params.get('quantity')
        warehouse_id = request.query_params.get('warehouse_id')

        if not all([product_id, unit_id, quantity, warehouse_id]):
            return Response({
                'error': 'All parameters are required: product_id, unit_id, quantity, warehouse_id'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = ProductService.check_stock_availability(
                product_id=product_id,
                unit_id=unit_id,
                quantity=quantity,
                warehouse_id=warehouse_id
            )
            return Response({
                "message": "Stock check completed",
                "data": result
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "error": "Error checking stock",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TestApi(APIView):
    def get(self, request):

        unit_category = UnitCategory.objects.first()
        print(unit_category.get_base_unit().name)
        return Response({
            "message": "Test API"
        }, status=status.HTTP_200_OK)
