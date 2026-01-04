from .models import Sale, SaleItem
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from product.models import Product
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db import IntegrityError
from .services.sale_service import SaleService
from .serializers import SaleSerializer


class SaleAPIView(APIView):
    def get(self, request, pk=None):
        """
        Retrieve a single sale by pk or list all sales.
        Company-filtered: only shows sales belonging to user's company.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        if pk:
            sale = get_object_or_404(
                Sale.objects.filter(company=request.company)
                .select_related('customer', 'warehouse', 'created_by', 'company')
                .prefetch_related(
                    Prefetch('items', queryset=SaleItem.objects.select_related(
                        'product', 'unit'))
                ),
                pk=pk
            )
            serializer = SaleSerializer(sale)
            return Response({"message": "Sale retrieved successfully", "data": serializer.data}, status=status.HTTP_200_OK)
        else:
            sales = Sale.objects.filter(company=request.company).select_related(
                'customer', 'warehouse', 'created_by', 'company'
            ).prefetch_related(
                Prefetch('items', queryset=SaleItem.objects.select_related(
                    'product', 'unit'))
            ).all().order_by('-created_at')
            serializer = SaleSerializer(sales, many=True)
            return Response({"message": "Sales retrieved successfully", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Create a new sale.
        Company-aware: automatically sets company from request context.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            sale = SaleService.create_sale(data, user, request.company)
            serializer = SaleSerializer(sale)
            return Response({
                "message": "Sale created successfully",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            error_details = e.detail if hasattr(e, 'detail') else str(e)
            return Response({
                "error": "Validation error",
                "details": error_details
            }, status=status.HTTP_400_BAD_REQUEST)

        except IntegrityError as e:
            return Response({
                "error": "Database integrity error",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, pk=None):
        """
        Update an existing sale.
        Company-aware: can only update sales belonging to user's company.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Sale ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        data = request.data
        data['id'] = pk  # Add id to data for serializer validation
        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            sale = SaleService.update_sale(data, user, request.company)
            serializer = SaleSerializer(sale)
            return Response({
                "message": "Sale updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            error_details = e.detail if hasattr(e, 'detail') else str(e)
            return Response({
                "error": "Validation error",
                "details": error_details
            }, status=status.HTTP_400_BAD_REQUEST)

        except IntegrityError as e:
            return Response({
                "error": "Database integrity error",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk=None):
        """
        Delete a sale.
        Company-aware: can only delete sales belonging to user's company.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Sale ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            sale = get_object_or_404(Sale.objects.filter(
                company=request.company), pk=pk)
            sale.delete()
            return Response({
                "message": "Sale deleted successfully"
            }, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({
                "error": "Failed to delete sale",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
