from .models import Purchase, PurchaseItem, PurchaseReturn, PurchaseReturnItem, PurchaseReturnStatus
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
from .services.purchase_service import PurchaseService
from .services.pdf_service import PurchaseInvoicePDF
from .serializers import PurchaseSerializer
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from payment.models import Payment, PaymentType, PaymentMethod, PaymentStatus as PayStatus
from payment.services.payment_fifo_service import PaymentFIFOService
from accounting.services.ledger_service import LedgerService


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
            active_returns_qs = PurchaseReturn.objects.filter(
                company=request.company,
                status__in=[PurchaseReturnStatus.PENDING, PurchaseReturnStatus.COMPLETED]
            ).prefetch_related(
                Prefetch(
                    'items',
                    queryset=PurchaseReturnItem.objects.select_related('product', 'unit'),
                    to_attr='active_items'
                )
            )

            purchase = get_object_or_404(
                Purchase.objects.filter(company=request.company)
                .select_related('supplier', 'warehouse', 'created_by', 'company')
                .prefetch_related(
                    Prefetch('items', queryset=PurchaseItem.objects.select_related(
                        'product', 'unit')),
                    Prefetch('returns', queryset=active_returns_qs, to_attr='active_returns')
                ),
                pk=pk
            )
            serializer = PurchaseSerializer(purchase)
            return Response({"message": "Purchase retrieved successfully", "data": serializer.data}, status=status.HTTP_200_OK)
        else:
            # Get base queryset
            active_returns_qs = PurchaseReturn.objects.filter(
                company=request.company,
                status__in=[PurchaseReturnStatus.PENDING, PurchaseReturnStatus.COMPLETED]
            ).prefetch_related(
                Prefetch(
                    'items',
                    queryset=PurchaseReturnItem.objects.select_related('product', 'unit'),
                    to_attr='active_items'
                )
            )

            purchases = Purchase.objects.filter(company=request.company).select_related(
                'supplier', 'warehouse', 'created_by', 'company'
            ).prefetch_related(
                Prefetch('items', queryset=PurchaseItem.objects.select_related(
                    'product', 'unit')),
                Prefetch('returns', queryset=active_returns_qs, to_attr='active_returns')
            )

            # Apply search filter
            search_query = request.query_params.get('search', '').strip()
            if search_query:
                search_filter = (
                    Q(invoice_number__icontains=search_query) |
                    Q(supplier__name__icontains=search_query) |
                    Q(warehouse__name__icontains=search_query)
                )
                # Try to search by ID if search query is numeric
                try:
                    search_id = int(search_query)
                    search_filter |= Q(id=search_id)
                except (ValueError, TypeError):
                    pass
                purchases = purchases.filter(search_filter)

            # Apply status filter
            status_filter = request.query_params.get('status', '').strip()
            if status_filter:
                purchases = purchases.filter(status=status_filter)

            # Apply payment_status filter
            payment_status_filter = request.query_params.get(
                'payment_status', '').strip()
            if payment_status_filter:
                purchases = purchases.filter(
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
                    total_count = purchases.count()
                    purchases = purchases.order_by('-created_at')[start:end]

                    serializer = PurchaseSerializer(purchases, many=True)
                    return Response({
                        "message": "Purchases retrieved successfully",
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
            purchases = purchases.order_by('-created_at')
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
            purchase = PurchaseService.create_purchase(
                data, user, request.company)
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


class PurchaseTakePaymentAPIView(APIView):
    """
    Take payment for a Purchase without updating items.
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

        purchase = get_object_or_404(
            Purchase.objects.filter(company=request.company).select_related('supplier', 'company'),
            pk=pk
        )

        try:
            with transaction.atomic():
                # Apply payment using FIFO logic
                # This will create payment records and update invoice status
                payment_date = request.data.get('date') or timezone.now().date()
                applied_payments = PaymentFIFOService.apply_payment_to_invoices(
                    payment_amount=amount,
                    party=purchase.supplier,
                    invoice_type='purchase',
                    company=request.company,
                    user=user,
                    specific_invoice=purchase,
                    payment_date=payment_date
                )
                
                # Reload purchase to get updated status
                purchase.refresh_from_db()

                serializer = PurchaseSerializer(purchase)
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

    def put(self, request, pk=None):
        """
        Update an existing purchase.
        Company-aware: can only update purchases belonging to user's company.
        Prevents editing completed purchases.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Purchase ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if purchase exists
        purchase = get_object_or_404(
            Purchase.objects.filter(company=request.company),
            pk=pk
        )

        # Get new status from request data
        new_status = request.data.get('status', purchase.status)
        old_status = purchase.status

        # Validate status transitions:
        # - pending → completed or cancelled: allowed
        # - completed → cancelled: allowed
        # - cancelled → cannot be changed (locked)
        # - completed → pending: NOT allowed

        # Prevent invalid status transitions
        if old_status == 'completed' and new_status == 'pending':
            return Response({
                "error": "Cannot change status from completed to pending"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Block all status changes from cancelled invoices
        if old_status == 'cancelled':
            return Response({
                "error": "Cannot change status of a cancelled purchase"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Allow status changes from completed to cancelled
        # The service layer will handle inventory/ledger reversals appropriately

        data = request.data
        data['id'] = pk  # Add id to data for serializer validation
        user = request.user if request.user.is_authenticated else None

        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            purchase = PurchaseService.update_purchase(
                data, user, request.company)
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
            purchase = get_object_or_404(
                Purchase.objects.filter(company=request.company), pk=pk)
            purchase.delete()
            return Response({
                "message": "Purchase deleted successfully"
            }, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({
                "error": "Failed to delete purchase",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class PurchaseInvoicePDFView(APIView):
    """
    Generate and download PDF invoice for a purchase.
    Company-filtered: can only access purchases belonging to user's company.
    """

    def get(self, request, pk):
        """
        Generate and return PDF invoice for a purchase.

        Args:
            request: HTTP request object
            pk: Primary key of the purchase

        Returns:
            HttpResponse with PDF content or error response
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
            # Get purchase with all related data
            purchase = get_object_or_404(
                Purchase.objects.filter(company=request.company)
                .select_related('supplier', 'warehouse', 'company', 'created_by')
                .prefetch_related(
                    Prefetch('items', queryset=PurchaseItem.objects.select_related(
                        'product', 'unit'))
                ),
                pk=pk
            )

            # Generate PDF
            pdf_generator = PurchaseInvoicePDF(purchase)
            return pdf_generator.generate()

        except Exception as e:
            return Response({
                "error": "Failed to generate PDF",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== Purchase Return Views ====================

class PurchaseReturnAPIView(APIView):
    """API view for purchase returns"""

    def get(self, request, pk=None):
        """Get single return or list all returns"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        if pk:
            # Get single purchase return with items
            from purchase.serializers import PurchaseReturnSerializer
            from purchase.models import PurchaseReturn

            purchase_return = get_object_or_404(
                PurchaseReturn.objects.filter(company=request.company)
                .select_related('purchase', 'supplier', 'warehouse', 'created_by')
                .prefetch_related('items__product', 'items__unit'),
                pk=pk
            )

            serializer = PurchaseReturnSerializer(purchase_return)
            return Response({
                "message": "Purchase return retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        # List all purchase returns
        from purchase.serializers import PurchaseReturnSerializer
        from purchase.models import PurchaseReturn

        returns = PurchaseReturn.objects.filter(company=request.company)\
            .select_related('purchase', 'supplier', 'warehouse', 'created_by')\
            .prefetch_related('items__product', 'items__unit')

        # Apply filters
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            from django.db.models import Q
            returns = returns.filter(
                Q(return_number__icontains=search_query) |
                Q(supplier__name__icontains=search_query) |
                Q(purchase__invoice_number__icontains=search_query)
            )

        status_filter = request.query_params.get('status', '').strip()
        if status_filter:
            returns = returns.filter(status=status_filter)

        supplier_id = request.query_params.get('supplier_id', '').strip()
        if supplier_id:
            returns = returns.filter(supplier_id=supplier_id)

        start_date = request.query_params.get('start_date', '').strip()
        end_date = request.query_params.get('end_date', '').strip()
        if start_date:
            returns = returns.filter(return_date__gte=start_date)
        if end_date:
            returns = returns.filter(return_date__lte=end_date)

        # Pagination
        page = request.query_params.get('page', None)
        page_size = request.query_params.get('page_size', None)

        if page and page_size:
            try:
                page = int(page)
                page_size = int(page_size)
                start = (page - 1) * page_size
                end = start + page_size
                total_count = returns.count()
                returns = returns.order_by(
                    '-return_date', '-created_at')[start:end]

                serializer = PurchaseReturnSerializer(returns, many=True)
                return Response({
                    "message": "Purchase returns retrieved successfully",
                    "data": serializer.data,
                    "count": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 0
                }, status=status.HTTP_200_OK)
            except (ValueError, TypeError):
                pass

        # Return all if no pagination
        returns = returns.order_by('-return_date', '-created_at')
        serializer = PurchaseReturnSerializer(returns, many=True)
        return Response({
            "message": "Purchase returns retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        """Create new purchase return"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        user = request.user if request.user.is_authenticated else None
        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        from purchase.serializers import PurchaseReturnInputSerializer, PurchaseReturnSerializer
        from purchase.services.purchase_return_service import PurchaseReturnService

        serializer = PurchaseReturnInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            # Create purchase return using service
            purchase_return = PurchaseReturnService.create_purchase_return(
                data=data,
                company=request.company,
                user=user
            )

            serializer_output = PurchaseReturnSerializer(purchase_return)
            return Response({
                "message": "Purchase return created successfully",
                "data": serializer_output.data
            }, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            return Response({
                "error": "Validation error",
                "details": e.detail if hasattr(e, 'detail') else str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "Internal server error",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk=None):
        """Delete (cancel) purchase return"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Purchase return ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user if request.user.is_authenticated else None
        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            from purchase.services.purchase_return_service import PurchaseReturnService

            # Cancel the return
            purchase_return = PurchaseReturnService.cancel_purchase_return(
                purchase_return_id=pk,
                company=request.company,
                user=user
            )

            return Response({
                "message": "Purchase return cancelled successfully"
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({
                "error": "Validation error",
                "details": e.detail if hasattr(e, 'detail') else str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "Failed to cancel purchase return",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class PurchaseReturnStatusAPIView(APIView):
    """API view for updating purchase return status"""

    def post(self, request, pk):
        """Update purchase return status"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        user = request.user if request.user.is_authenticated else None
        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        from purchase.serializers import PurchaseReturnStatusUpdateSerializer, PurchaseReturnSerializer
        from purchase.services.purchase_return_service import PurchaseReturnService
        from purchase.models import PurchaseReturnStatus

        serializer = PurchaseReturnStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data['status']

        try:
            if new_status == PurchaseReturnStatus.COMPLETED:
                # Complete the return
                purchase_return = PurchaseReturnService.complete_purchase_return(
                    purchase_return_id=pk,
                    company=request.company,
                    user=user
                )
            elif new_status == PurchaseReturnStatus.CANCELLED:
                # Cancel the return
                purchase_return = PurchaseReturnService.cancel_purchase_return(
                    purchase_return_id=pk,
                    company=request.company,
                    user=user
                )
            else:
                return Response({
                    "error": "Invalid status transition"
                }, status=status.HTTP_400_BAD_REQUEST)

            serializer_output = PurchaseReturnSerializer(purchase_return)
            return Response({
                "message": f"Purchase return {new_status} successfully",
                "data": serializer_output.data
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({
                "error": "Validation error",
                "details": e.detail if hasattr(e, 'detail') else str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": "Failed to update status",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PurchaseReturnCompleteAPIView(APIView):
    """API view to complete a purchase return"""

    def post(self, request, pk):
        """
        Complete a purchase return.
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
            from purchase.services.purchase_return_service import PurchaseReturnService
            from purchase.serializers import PurchaseReturnSerializer
            
            purchase_return = PurchaseReturnService.complete_purchase_return(
                pk, request.company, user)
            serializer = PurchaseReturnSerializer(purchase_return)
            return Response({
                "message": "Purchase return completed successfully",
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


class PurchaseReturnCancelAPIView(APIView):
    """API view to cancel a purchase return"""

    def post(self, request, pk):
        """
        Cancel a purchase return.
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
            from purchase.services.purchase_return_service import PurchaseReturnService
            from purchase.serializers import PurchaseReturnSerializer
            
            purchase_return = PurchaseReturnService.cancel_purchase_return(
                pk, request.company, user)
            serializer = PurchaseReturnSerializer(purchase_return)
            return Response({
                "message": "Purchase return cancelled successfully",
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


class PurchaseReturnableItemsAPIView(APIView):
    """API view to get returnable items for a purchase"""

    def get(self, request, purchase_id):
        """
        Get list of items that can be returned from a purchase.
        Shows original quantities and already returned quantities.
        """
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            from purchase.services.purchase_return_service import PurchaseReturnService
            import traceback
            
            returnable_items = PurchaseReturnService.get_returnable_items(
                purchase_id, request.company)
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
            # Print full traceback for debugging
            import traceback
            traceback.print_exc()
            return Response({
                "error": "Internal server error",
                "details": str(e),
                "traceback": traceback.format_exc()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def test(request):
    product = get_object_or_404(Product, id=1)
    product.update(name='update katari')
    return HttpResponse("Purchase app is working fine!")
