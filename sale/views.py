from .models import Sale, SaleItem
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Q
from product.models import Product
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db import IntegrityError
from .services.sale_service import SaleService
from .services.pdf_service import SaleInvoicePDF
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
            # Get base queryset
            sales = Sale.objects.filter(company=request.company).select_related(
                'customer', 'warehouse', 'created_by', 'company'
            ).prefetch_related(
                Prefetch('items', queryset=SaleItem.objects.select_related(
                    'product', 'unit'))
            )

            # Apply search filter
            search_query = request.query_params.get('search', '').strip()
            if search_query:
                search_filter = (
                    Q(invoice_number__icontains=search_query) |
                    Q(customer__name__icontains=search_query) |
                    Q(warehouse__name__icontains=search_query)
                )
                # Try to search by ID if search query is numeric
                try:
                    search_id = int(search_query)
                    search_filter |= Q(id=search_id)
                except (ValueError, TypeError):
                    pass
                sales = sales.filter(search_filter)

            # Apply status filter
            status_filter = request.query_params.get('status', '').strip()
            if status_filter:
                sales = sales.filter(status=status_filter)

            # Apply payment_status filter
            payment_status_filter = request.query_params.get(
                'payment_status', '').strip()
            if payment_status_filter:
                sales = sales.filter(
                    payment_status=payment_status_filter)

            # Apply pagination if needed
            page = request.query_params.get('page', None)
            page_size = request.query_params.get('page_size', None)

            if page and page_size:
                try:
                    page = int(page)
                    page_size = int(page_size)
                    start = (page - 1) * page_size
                    end = start + page_size
                    total_count = sales.count()
                    sales = sales.order_by('-created_at')[start:end]

                    serializer = SaleSerializer(sales, many=True)
                    return Response({
                        "message": "Sales retrieved successfully",
                        "data": serializer.data,
                        "count": total_count,
                        "page": page,
                        "page_size": page_size,
                        "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 0
                    }, status=status.HTTP_200_OK)
                except (ValueError, TypeError):
                    # Invalid pagination params, return all
                    pass

            # Return all if no pagination
            sales = sales.order_by('-created_at')
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
            sale = SaleService.create_sale(
                data, user, request.company)
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
        Prevents editing completed sales.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Sale ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if sale exists and is not completed
        sale = get_object_or_404(
            Sale.objects.filter(company=request.company),
            pk=pk
        )

        if sale.status == 'delivered':
            return Response({
                "error": "Cannot edit a delivered sale"
            }, status=status.HTTP_400_BAD_REQUEST)

        data = request.data
        data['id'] = pk  # Add id to data for serializer validation
        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            sale = SaleService.update_sale(
                data, user, request.company)
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
            sale = get_object_or_404(
                Sale.objects.filter(company=request.company), pk=pk)
            sale.delete()
            return Response({
                "message": "Sale deleted successfully"
            }, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({
                "error": "Failed to delete sale",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class SaleInvoicePDFView(APIView):
    """
    Generate and download PDF invoice for a sale.
    Company-filtered: can only access sales belonging to user's company.
    """

    def get(self, request, pk):
        """
        Generate and return PDF invoice for a sale.

        Args:
            request: HTTP request object
            pk: Primary key of the sale

        Returns:
            HttpResponse with PDF content or error response
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
            # Get sale with all related data
            sale = get_object_or_404(
                Sale.objects.filter(company=request.company)
                .select_related('customer', 'warehouse', 'company', 'created_by')
                .prefetch_related(
                    Prefetch('items', queryset=SaleItem.objects.select_related(
                        'product', 'unit'))
                ),
                pk=pk
            )

            # Generate PDF
            pdf_generator = SaleInvoicePDF(sale)
            return pdf_generator.generate()

        except Exception as e:
            return Response({
                "error": "Failed to generate PDF",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
