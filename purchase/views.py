from .models import Purchase, PurchaseItem
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from product.models import Product
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets, filters
from rest_framework.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db import IntegrityError
from .services.purchase_service import PurchaseService
from .serializers import PurchaseSerializer
import django_filters


class CustomSearchFilter(filters.SearchFilter):
    def get_search_fields(self, view, request):
        if request.query_params.get('inv'):
            return ['invoice_number']
        return super().get_search_fields(view, request)


class ApplicationFilter(django_filters.FilterSet):
    start_date = django_filters.CharFilter(
        field_name='invoice_number', lookup_expr='')

    class Meta:
        model = Purchase
        fields = ['invoice_number']


class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['invoice_date']
    ordering = ['-invoice_date']


class PurchaseAPIView(APIView):
    def get(self, request, pk=None):
        """
        Retrieve a single purchase by pk or list all purchases
        """
        if pk:
            purchase = get_object_or_404(
                Purchase.objects.select_related(
                    'supplier', 'warehouse', 'created_by')
                .prefetch_related(
                    Prefetch('items', queryset=PurchaseItem.objects.select_related(
                        'product', 'unit'))
                ),
                pk=pk
            )
            serializer = PurchaseSerializer(purchase)
            return Response({"message": "Purchase retrieved successfully", "data": serializer.data}, status=status.HTTP_200_OK)
        else:
            purchases = Purchase.objects.select_related('supplier', 'warehouse', 'created_by').prefetch_related(
                Prefetch('items', queryset=PurchaseItem.objects.select_related(
                    'product', 'unit'))
            ).all().order_by('-created_at')
            serializer = PurchaseSerializer(purchases, many=True)
            return Response({"message": "Purchases retrieved successfully", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Create a new purchase
        """
        data = request.data
        user = request.user if request.user.is_authenticated else User.objects.first()

        try:
            purchase = PurchaseService.create_purchase(data, user)
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
        Update an existing purchase
        """
        if not pk:
            return Response({
                "error": "Purchase ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        data = request.data
        data['id'] = pk  # Add id to data for serializer validation
        user = request.user if request.user.is_authenticated else User.objects.first()

        try:
            purchase = PurchaseService.update_purchase(data, user)
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
        Delete a purchase
        """
        if not pk:
            return Response({
                "error": "Purchase ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            purchase = get_object_or_404(Purchase, pk=pk)
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
