from .models import Purchase, PurchaseItem
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
from .services.purchase_service import PurchaseService
from .serializers import PurchaseSerializer


class PurchaseAPIView(APIView):
    def get(self, request, pk=None):
        """
        Retrieve a single purchase by pk or list all purchases.
        Company-filtered: only shows purchases belonging to user's company.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        if pk:
            purchase = get_object_or_404(
                Purchase.objects.filter(company=request.company)
                .select_related('supplier', 'warehouse', 'created_by', 'company')
                .prefetch_related(
                    Prefetch('items', queryset=PurchaseItem.objects.select_related('product', 'unit'))
                ),
                pk=pk
            )
            serializer = PurchaseSerializer(purchase)
            return Response({"message": "Purchase retrieved successfully", "data": serializer.data}, status=status.HTTP_200_OK)
        else:
            purchases = Purchase.objects.filter(company=request.company).select_related(
                'supplier', 'warehouse', 'created_by', 'company'
            ).prefetch_related(
                Prefetch('items', queryset=PurchaseItem.objects.select_related('product', 'unit'))
            ).all().order_by('-created_at')
            serializer = PurchaseSerializer(purchases, many=True)
            return Response({"message": "Purchases retrieved successfully", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Create a new purchase.
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
            purchase = PurchaseService.create_purchase(data, user, request.company)
            serializer = PurchaseSerializer(purchase)
            return Response({
                "message": "Purchase created successfully",
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
        Update an existing purchase.
        Company-aware: can only update purchases belonging to user's company.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Purchase ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        data = request.data
        data['id'] = pk  # Add id to data for serializer validation
        user = request.user if request.user.is_authenticated else None
        
        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            purchase = PurchaseService.update_purchase(data, user, request.company)
            serializer = PurchaseSerializer(purchase)
            return Response({
                "message": "Purchase updated successfully",
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
        Delete a purchase.
        Company-aware: can only delete purchases belonging to user's company.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Purchase ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            purchase = get_object_or_404(Purchase.objects.filter(company=request.company), pk=pk)
            purchase.delete()
            return Response({
                "message": "Purchase deleted successfully"
            }, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({
                "error": "Failed to delete purchase",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


def test(request):
    product = get_object_or_404(Product, id=1)
    product.update(name='update katari')
    return HttpResponse("Purchase app is working fine!")
