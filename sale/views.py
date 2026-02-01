from .models import Sale, SaleItem, SaleReturn, SaleReturnItem, SaleReturnStatus
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Q
from django.conf import settings
from product.models import Product
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db import IntegrityError
from .services.sale_service import SaleService
from .services.sale_return_service import SaleReturnService
from .services.pdf_service import SaleInvoicePDF
from .serializers import SaleSerializer, SaleReturnSerializer
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from payment.models import Payment, PaymentType, PaymentMethod, PaymentStatus as PayStatus
from payment.services.payment_fifo_service import PaymentFIFOService
from accounting.services.ledger_service import LedgerService


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
                    Prefetch(
                        'items',
                        queryset=SaleItem.objects.select_related('product', 'unit').prefetch_related(
                            Prefetch(
                                'return_items',
                                queryset=SaleReturnItem.objects.filter(
                                    sale_return__status__in=[
                                        SaleReturnStatus.PENDING, SaleReturnStatus.COMPLETED
                                    ]
                                ).select_related('sale_return'),
                                to_attr='active_return_items'
                            )
                        )
                    )
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
                Prefetch(
                    'items',
                    queryset=SaleItem.objects.select_related('product', 'unit').prefetch_related(
                        Prefetch(
                            'return_items',
                            queryset=SaleReturnItem.objects.filter(
                                sale_return__status__in=[
                                    SaleReturnStatus.PENDING, SaleReturnStatus.COMPLETED
                                ]
                            ).select_related('sale_return'),
                            to_attr='active_return_items'
                        )
                    )
                )
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
                sales = sales.filter(payment_status=payment_status_filter)

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
        Prevents editing delivered sales.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Sale ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if sale exists
        sale = get_object_or_404(
            Sale.objects.filter(company=request.company),
            pk=pk
        )

        # Get new status from request data
        new_status = request.data.get('status', sale.status)
        old_status = sale.status

        # Validate status transitions:
        # - pending → delivered or cancelled: allowed
        # - delivered → CANNOT be cancelled (use sale return instead)
        # - cancelled → cannot be changed (locked)
        # - delivered → pending: NOT allowed

        # Prevent invalid status transitions
        if old_status == 'delivered' and new_status == 'pending':
            return Response({
                "error": "Cannot change status from delivered to pending"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Prevent cancelling delivered sales - use sale return instead
        if old_status == 'delivered' and new_status == 'cancelled':
            return Response({
                "error": "Cannot cancel a delivered sale. Please create a Sale Return instead."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Block all status changes from cancelled invoices
        if old_status == 'cancelled':
            return Response({
                "error": "Cannot change status of a cancelled invoice"
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


class SaleTakePaymentAPIView(APIView):
    """
    Take payment for a Sale without updating items (safe with SaleReturns).
    Cash-only for now.
    """

    def post(self, request, pk):
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        user = request.user if request.user.is_authenticated else None
        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            amount = Decimal(str(request.data.get('amount', '0')))
        except Exception:
            return Response({
                "error": "Validation error",
                "details": {"amount": ["Invalid amount"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({
                "error": "Validation error",
                "details": {"amount": ["Amount must be greater than zero"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        sale = get_object_or_404(
            Sale.objects.filter(company=request.company).select_related(
                'customer', 'company'),
            pk=pk
        )

        try:
            with transaction.atomic():
                # Apply payment using FIFO logic
                # This will create payment records and update invoice status
                payment_date = request.data.get('date') or timezone.now().date()
                applied_payments = PaymentFIFOService.apply_payment_to_invoices(
                    payment_amount=amount,
                    party=sale.customer,
                    invoice_type='sale',
                    company=request.company,
                    user=user,
                    specific_invoice=sale,
                    payment_date=payment_date
                )
                
                # Reload sale to get updated status
                sale.refresh_from_db()

                serializer = SaleSerializer(sale)
                return Response({
                    "message": "Payment taken successfully",
                    "data": serializer.data,
                    "applied_to_invoices": [
                        {
                            "invoice_id": inv.id,
                            "invoice_number": inv.invoice_number or str(inv.id),
                            "applied_amount": float(applied_amount)
                        }
                        for inv, applied_amount in applied_payments
                    ]
                }, status=status.HTTP_200_OK)

        except ValidationError as e:
            error_details = e.detail if hasattr(e, 'detail') else str(e)
            return Response({
                "error": "Validation error",
                "details": error_details
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SaleInvoicePDFView(APIView):
    """
    Generate and download PDF invoice for a sale.
    Company-filtered: can only access sales belonging to user's company.
    """

    def get(self, request, pk):
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

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

        except ImportError as e:
            # Handle missing PDF library
            return Response({
                "error": "PDF generation library not available",
                "details": str(e),
                "message": "Please install either 'weasyprint' or 'xhtml2pdf': pip install weasyprint"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except ValueError as e:
            # Handle missing required data
            return Response({
                "error": "Invalid sale data",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Log the full error for debugging
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            error_traceback = traceback.format_exc()
            logger.error(
                f"Error generating PDF for sale {pk}: {str(e)}\n{error_traceback}", exc_info=True)
            return Response({
                "error": "Failed to generate PDF",
                "details": str(e),
                "traceback": error_traceback if settings.DEBUG else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ================= SALE RETURN VIEWS =================

class SaleReturnAPIView(APIView):
    """API view for sale returns - create, list, retrieve, update"""

    def get(self, request, pk=None):
        """
        Retrieve a single sale return by pk or list all sale returns.
        Company-filtered: only shows returns belonging to user's company.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        if pk:
            sale_return = get_object_or_404(
                SaleReturn.objects.filter(company=request.company)
                .select_related('sale', 'customer', 'warehouse', 'created_by', 'company')
                .prefetch_related(
                    Prefetch('items', queryset=SaleReturnItem.objects.select_related(
                        'product', 'unit', 'sale_item'))
                ),
                pk=pk
            )
            serializer = SaleReturnSerializer(sale_return)
            return Response({
                "message": "Sale return retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        else:
            # Get base queryset
            returns = SaleReturn.objects.filter(company=request.company).select_related(
                'sale', 'customer', 'warehouse', 'created_by', 'company'
            ).prefetch_related(
                Prefetch('items', queryset=SaleReturnItem.objects.select_related(
                    'product', 'unit', 'sale_item'))
            )

            # Apply search filter
            search_query = request.query_params.get('search', '').strip()
            if search_query:
                search_filter = (
                    Q(return_number__icontains=search_query) |
                    Q(sale__invoice_number__icontains=search_query) |
                    Q(customer__name__icontains=search_query)
                )
                # Try to search by ID if search query is numeric
                try:
                    search_id = int(search_query)
                    search_filter |= Q(id=search_id)
                except (ValueError, TypeError):
                    pass
                returns = returns.filter(search_filter)

            # Apply status filter
            status_filter = request.query_params.get('status', '').strip()
            if status_filter:
                returns = returns.filter(status=status_filter)

            # Apply refund_status filter
            refund_status_filter = request.query_params.get(
                'refund_status', '').strip()
            if refund_status_filter:
                returns = returns.filter(refund_status=refund_status_filter)

            # Apply sale filter
            sale_id = request.query_params.get('sale_id', '').strip()
            if sale_id:
                returns = returns.filter(sale_id=sale_id)

            # Apply pagination if needed
            page = request.query_params.get('page', None)
            page_size = request.query_params.get('page_size', None)

            if page and page_size:
                try:
                    page = int(page)
                    page_size = int(page_size)
                    start = (page - 1) * page_size
                    end = start + page_size
                    total_count = returns.count()
                    returns = returns.order_by('-created_at')[start:end]

                    serializer = SaleReturnSerializer(returns, many=True)
                    return Response({
                        "message": "Sale returns retrieved successfully",
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
            returns = returns.order_by('-created_at')
            serializer = SaleReturnSerializer(returns, many=True)
            return Response({
                "message": "Sale returns retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Create a new sale return.
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
            sale_return = SaleReturnService.create_sale_return(
                data, user, request.company)
            serializer = SaleReturnSerializer(sale_return)
            return Response({
                "message": "Sale return created successfully",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            error_details = e.detail if hasattr(e, 'detail') else str(e)
            return Response({
                "error": "Validation error",
                "details": error_details
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, pk=None):
        """
        Update an existing sale return.
        Can only update returns in PENDING status.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Sale return ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if sale return exists
        sale_return = get_object_or_404(
            SaleReturn.objects.filter(company=request.company),
            pk=pk
        )

        data = request.data
        data['id'] = pk
        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            sale_return = SaleReturnService.update_sale_return(
                data, user, request.company)
            serializer = SaleReturnSerializer(sale_return)
            return Response({
                "message": "Sale return updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            error_details = e.detail if hasattr(e, 'detail') else str(e)
            return Response({
                "error": "Validation error",
                "details": error_details
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk=None):
        """
        Delete a sale return.
        Can only delete returns in PENDING status.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Sale return ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            sale_return = get_object_or_404(
                SaleReturn.objects.filter(company=request.company),
                pk=pk
            )

            # Only allow deletion of pending returns
            if sale_return.status != 'pending':
                return Response({
                    "error": f"Cannot delete sale return with status '{sale_return.status}'. Only pending returns can be deleted."
                }, status=status.HTTP_400_BAD_REQUEST)

            sale_return.delete()
            return Response({
                "message": "Sale return deleted successfully"
            }, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({
                "error": "Failed to delete sale return",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class SaleReturnCompleteAPIView(APIView):
    """API view to complete a sale return"""

    def post(self, request, pk):
        """
        Complete a sale return.
        This will update inventory and create accounting entries.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            sale_return = SaleReturnService.complete_sale_return(
                pk, user, request.company)
            serializer = SaleReturnSerializer(sale_return)
            return Response({
                "message": "Sale return completed successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            error_details = e.detail if hasattr(e, 'detail') else str(e)
            return Response({
                "error": "Validation error",
                "details": error_details
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SaleReturnCancelAPIView(APIView):
    """API view to cancel a sale return"""

    def post(self, request, pk):
        """
        Cancel a sale return.
        Can only cancel returns in PENDING status.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            sale_return = SaleReturnService.cancel_sale_return(
                pk, user, request.company)
            serializer = SaleReturnSerializer(sale_return)
            return Response({
                "message": "Sale return cancelled successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            error_details = e.detail if hasattr(e, 'detail') else str(e)
            return Response({
                "error": "Validation error",
                "details": error_details
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SaleReturnableItemsAPIView(APIView):
    """API view to get returnable items for a sale"""

    def get(self, request, sale_id):
        """
        Get list of items that can be returned from a sale.
        Shows original quantities and already returned quantities.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            returnable_items = SaleReturnService.get_returnable_items(
                sale_id, request.company)
            return Response({
                "message": "Returnable items retrieved successfully",
                "data": returnable_items
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            error_details = e.detail if hasattr(e, 'detail') else str(e)
            return Response({
                "error": "Validation error",
                "details": error_details
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
