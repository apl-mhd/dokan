from django.shortcuts import get_object_or_404
from django.db.models import Q, Prefetch
from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from payment.models import Payment, PaymentType, PaymentMethod, PaymentStatus as PayStatus
from payment.serializers import (
    PaymentSerializer,
    PaymentInputSerializer,
    PaymentUpdateSerializer
)
from payment.services.payment_fifo_service import PaymentFIFOService
from customer.models import Customer
from supplier.models import Supplier
from accounting.services.ledger_service import LedgerService


class PaymentAPIView(APIView):
    """Unified API view for all payments (customer and supplier)"""

    def get(self, request, pk=None):
        """Get single payment or list all payments"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        if pk:
            payment = get_object_or_404(
                Payment.objects.filter(company=request.company)
                .select_related('customer', 'supplier', 'sale', 'purchase', 'company', 'created_by'),
                pk=pk
            )
            serializer = PaymentSerializer(payment)
            return Response({
                "message": "Payment retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        # List all payments
        payments = Payment.objects.filter(company=request.company).select_related(
            'customer', 'supplier', 'sale', 'purchase', 'company', 'created_by'
        )

        # Apply filters
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            search_filter = (
                Q(customer__name__icontains=search_query) |
                Q(supplier__name__icontains=search_query) |
                Q(reference_number__icontains=search_query) |
                Q(sale__invoice_number__icontains=search_query) |
                Q(purchase__invoice_number__icontains=search_query)
            )
            try:
                search_id = int(search_query)
                search_filter |= Q(id=search_id)
            except (ValueError, TypeError):
                pass
            payments = payments.filter(search_filter)

        # Filter by payment type
        payment_type = request.query_params.get('payment_type', '').strip()
        if payment_type:
            payments = payments.filter(payment_type=payment_type)

        # Filter by payment method
        payment_method = request.query_params.get('payment_method', '').strip()
        if payment_method:
            payments = payments.filter(payment_method=payment_method)

        # Filter by status
        payment_status = request.query_params.get('status', '').strip()
        if payment_status:
            payments = payments.filter(status=payment_status)

        # Filter by customer
        customer_id = request.query_params.get('customer_id', '').strip()
        if customer_id:
            payments = payments.filter(customer_id=customer_id)

        # Filter by supplier
        supplier_id = request.query_params.get('supplier_id', '').strip()
        if supplier_id:
            payments = payments.filter(supplier_id=supplier_id)

        # Filter by date range
        start_date = request.query_params.get('start_date', '').strip()
        end_date = request.query_params.get('end_date', '').strip()
        if start_date:
            payments = payments.filter(date__gte=start_date)
        if end_date:
            payments = payments.filter(date__lte=end_date)

        # Pagination
        page = request.query_params.get('page', None)
        page_size = request.query_params.get('page_size', None)

        if page and page_size:
            try:
                page = int(page)
                page_size = int(page_size)
                start = (page - 1) * page_size
                end = start + page_size
                total_count = payments.count()
                payments = payments.order_by('-date', '-created_at')[start:end]

                serializer = PaymentSerializer(payments, many=True)
                return Response({
                    "message": "Payments retrieved successfully",
                    "data": serializer.data,
                    "count": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 0
                }, status=status.HTTP_200_OK)
            except (ValueError, TypeError):
                pass

        # Return all if no pagination
        payments = payments.order_by('-date', '-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response({
            "message": "Payments retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        """Create new payment (customer or supplier)"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        user = request.user if request.user.is_authenticated else None
        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        serializer = PaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            with db_transaction.atomic():
                payment_type = data['payment_type']

                # Get party (customer or supplier)
                customer = None
                supplier = None
                party = None

                if payment_type == PaymentType.RECEIVED:
                    customer = get_object_or_404(
                        Customer.objects.filter(company=request.company),
                        id=data['customer']
                    )
                    party = customer
                else:  # PaymentType.MADE
                    supplier = get_object_or_404(
                        Supplier.objects.filter(company=request.company),
                        id=data['supplier']
                    )
                    party = supplier

                # Get sale/purchase if provided
                sale = None
                purchase = None
                if data.get('sale'):
                    from sale.models import Sale
                    sale = get_object_or_404(
                        Sale.objects.filter(company=request.company),
                        id=data['sale']
                    )
                if data.get('purchase'):
                    from purchase.models import Purchase
                    purchase = get_object_or_404(
                        Purchase.objects.filter(company=request.company),
                        id=data['purchase']
                    )

                payment_status = data.get('status', 'completed')
                payment_method = data.get('payment_method', PaymentMethod.CASH)
                payment_amount = data['amount']
                
                # Apply FIFO for cash payments that are completed
                if (payment_method == PaymentMethod.CASH and 
                    payment_status == PayStatus.COMPLETED and 
                    payment_amount > 0):
                    
                    # Determine invoice type
                    invoice_type = 'sale' if payment_type == PaymentType.RECEIVED else 'purchase'
                    specific_invoice = sale if invoice_type == 'sale' else purchase
                    
                    # Apply payment using FIFO
                    payment_date = data.get('date') or timezone.now().date()
                    applied_payments = PaymentFIFOService.apply_payment_to_invoices(
                        payment_amount=payment_amount,
                        party=party,
                        invoice_type=invoice_type,
                        company=request.company,
                        user=user,
                        specific_invoice=specific_invoice,
                        payment_date=payment_date
                    )
                    
                    # Return response with FIFO information
                    # Note: Multiple payment records were created by FIFO service
                    # Query for payments created in this transaction (by date and party)
                    created_payments = Payment.objects.filter(
                        company=request.company,
                        payment_type=payment_type,
                        customer=customer if payment_type == PaymentType.RECEIVED else None,
                        supplier=supplier if payment_type == PaymentType.MADE else None,
                        payment_method=payment_method,
                        date=payment_date,
                        created_by=user
                    ).order_by('-created_at')[:len(applied_payments)]
                    
                    # Return the first payment for backward compatibility
                    first_payment = created_payments.first() if created_payments.exists() else None
                    serializer_output = PaymentSerializer(first_payment) if first_payment else None
                    
                    return Response({
                        "message": "Payment created successfully (FIFO applied)",
                        "data": serializer_output.data if serializer_output else None,
                        "applied_to_invoices": [
                            {
                                "invoice_id": inv.id,
                                "invoice_number": inv.invoice_number or str(inv.id),
                                "applied_amount": float(applied_amount)
                            }
                            for inv, applied_amount in applied_payments
                        ]
                    }, status=status.HTTP_201_CREATED)
                
                # For non-cash or non-completed payments, create payment normally
                payment = Payment.objects.create(
                    company=request.company,
                    payment_type=payment_type,
                    customer=customer,
                    supplier=supplier,
                    sale=sale,
                    purchase=purchase,
                    payment_method=payment_method,
                    amount=payment_amount,
                    date=data.get('date'),
                    reference_number=data.get('reference_number', ''),
                    account_number=data.get('account_number', ''),
                    account_holder_name=data.get('account_holder_name', ''),
                    bank_name=data.get('bank_name', ''),
                    branch_name=data.get('branch_name', ''),
                    status=payment_status,
                    notes=data.get('notes', ''),
                    created_by=user
                )

                # Create ledger entry only if payment status is completed
                if payment.status == 'completed' and payment.amount > 0:
                    payment_type_str = 'received' if payment_type == PaymentType.RECEIVED else 'made'
                    LedgerService.create_payment_ledger_entry(
                        payment, request.company, party, payment_type=payment_type_str
                    )
                    # Update party balance
                    LedgerService.update_party_balance(party, request.company)

                serializer_output = PaymentSerializer(payment)
                return Response({
                    "message": "Payment created successfully",
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

    def put(self, request, pk=None):
        """Update payment"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Payment ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user if request.user.is_authenticated else None
        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        payment = get_object_or_404(
            Payment.objects.filter(company=request.company),
            pk=pk
        )

        serializer = PaymentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            with db_transaction.atomic():
                old_status = payment.status
                old_amount = payment.amount

                # Update fields
                if 'payment_method' in data:
                    payment.payment_method = data['payment_method']
                if 'amount' in data:
                    payment.amount = data['amount']
                if 'date' in data:
                    payment.date = data['date']
                if 'reference_number' in data:
                    payment.reference_number = data['reference_number']
                if 'account_number' in data:
                    payment.account_number = data['account_number']
                if 'account_holder_name' in data:
                    payment.account_holder_name = data['account_holder_name']
                if 'bank_name' in data:
                    payment.bank_name = data['bank_name']
                if 'branch_name' in data:
                    payment.branch_name = data['branch_name']
                if 'status' in data:
                    payment.status = data['status']
                if 'notes' in data:
                    payment.notes = data['notes']

                payment.updated_by = user
                payment.save()

                # Handle ledger updates
                new_status = payment.status

                # If status changed or amount changed, update ledger
                if old_status != new_status or old_amount != payment.amount:
                    # Delete old ledger entries
                    LedgerService.delete_ledger_entries_for_object(
                        payment, request.company)

                    # Create new ledger entry if status is completed
                    if new_status == 'completed' and payment.amount > 0:
                        party = payment.get_party()
                        payment_type_str = 'received' if payment.payment_type == PaymentType.RECEIVED else 'made'
                        LedgerService.create_payment_ledger_entry(
                            payment, request.company, party, payment_type=payment_type_str
                        )

                    # Update party balance
                    party = payment.get_party()
                    LedgerService.update_party_balance(party, request.company)

                serializer_output = PaymentSerializer(payment)
                return Response({
                    "message": "Payment updated successfully",
                    "data": serializer_output.data
                }, status=status.HTTP_200_OK)

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
        """Delete payment"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Payment ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            with db_transaction.atomic():
                payment = get_object_or_404(
                    Payment.objects.filter(company=request.company),
                    pk=pk
                )
                party = payment.get_party()

                # Delete ledger entries first
                LedgerService.delete_ledger_entries_for_object(
                    payment, request.company)

                # Delete payment
                payment.delete()

                # Update party balance
                LedgerService.update_party_balance(party, request.company)

                return Response({
                    "message": "Payment deleted successfully"
                }, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({
                "error": "Failed to delete payment",
                "details": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


# Backward compatibility views (for existing frontend)
class CustomerPaymentAPIView(APIView):
    """Backward compatible view that filters to customer payments only"""

    def get(self, request, pk=None):
        """Get customer payments (payment_type='received')"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        if pk:
            payment = get_object_or_404(
                Payment.objects.filter(
                    company=request.company,
                    payment_type=PaymentType.RECEIVED
                ).select_related('customer', 'sale', 'company', 'created_by'),
                pk=pk
            )
            serializer = PaymentSerializer(payment)
            return Response({
                "message": "Payment retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        # List customer payments
        payments = Payment.objects.filter(
            company=request.company,
            payment_type=PaymentType.RECEIVED
        ).select_related('customer', 'sale', 'company', 'created_by')

        # Apply filters
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            search_filter = (
                Q(customer__name__icontains=search_query) |
                Q(reference_number__icontains=search_query) |
                Q(sale__invoice_number__icontains=search_query)
            )
            try:
                search_id = int(search_query)
                search_filter |= Q(id=search_id)
            except (ValueError, TypeError):
                pass
            payments = payments.filter(search_filter)

        payment_method = request.query_params.get('payment_method', '').strip()
        if payment_method:
            payments = payments.filter(payment_method=payment_method)

        payment_status = request.query_params.get('status', '').strip()
        if payment_status:
            payments = payments.filter(status=payment_status)

        start_date = request.query_params.get('start_date', '').strip()
        end_date = request.query_params.get('end_date', '').strip()
        if start_date:
            payments = payments.filter(date__gte=start_date)
        if end_date:
            payments = payments.filter(date__lte=end_date)

        # Pagination
        page = request.query_params.get('page', None)
        page_size = request.query_params.get('page_size', None)

        if page and page_size:
            try:
                page = int(page)
                page_size = int(page_size)
                start = (page - 1) * page_size
                end = start + page_size
                total_count = payments.count()
                payments = payments.order_by('-date', '-created_at')[start:end]

                serializer = PaymentSerializer(payments, many=True)
                return Response({
                    "message": "Payments retrieved successfully",
                    "data": serializer.data,
                    "count": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 0
                }, status=status.HTTP_200_OK)
            except (ValueError, TypeError):
                pass

        # Return all if no pagination
        payments = payments.order_by('-date', '-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response({
            "message": "Payments retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        """Create customer payment (automatically sets payment_type='received')"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        user = request.user if request.user.is_authenticated else None
        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Add payment_type to the data
        data = request.data.copy()
        data['payment_type'] = PaymentType.RECEIVED

        serializer = PaymentInputSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        try:
            with db_transaction.atomic():
                customer = get_object_or_404(
                    Customer.objects.filter(company=request.company),
                    id=validated_data['customer']
                )

                sale = None
                if validated_data.get('sale'):
                    from sale.models import Sale
                    sale = get_object_or_404(
                        Sale.objects.filter(company=request.company),
                        id=validated_data['sale']
                    )

                payment_status = validated_data.get('status', 'completed')
                payment_method = validated_data.get('payment_method', PaymentMethod.CASH)
                payment_amount = validated_data['amount']
                payment_date = validated_data.get('date') or timezone.now().date()
                
                # Apply FIFO for cash payments that are completed
                if (payment_method == PaymentMethod.CASH and 
                    payment_status == PayStatus.COMPLETED and 
                    payment_amount > 0):
                    
                    # Apply payment using FIFO
                    applied_payments = PaymentFIFOService.apply_payment_to_invoices(
                        payment_amount=payment_amount,
                        party=customer,
                        invoice_type='sale',
                        company=request.company,
                        user=user,
                        specific_invoice=sale,
                        payment_date=payment_date
                    )
                    
                    # Return response with FIFO information
                    created_payments = Payment.objects.filter(
                        company=request.company,
                        payment_type=PaymentType.RECEIVED,
                        customer=customer,
                        payment_method=payment_method,
                        date=payment_date,
                        created_by=user
                    ).order_by('-created_at')[:len(applied_payments)]
                    
                    first_payment = created_payments.first() if created_payments.exists() else None
                    serializer_output = PaymentSerializer(first_payment) if first_payment else None
                    
                    return Response({
                        "message": "Customer payment created successfully (FIFO applied)",
                        "data": serializer_output.data if serializer_output else None,
                        "applied_to_invoices": [
                            {
                                "invoice_id": inv.id,
                                "invoice_number": inv.invoice_number or str(inv.id),
                                "applied_amount": float(applied_amount)
                            }
                            for inv, applied_amount in applied_payments
                        ]
                    }, status=status.HTTP_201_CREATED)

                # For non-cash or non-completed payments, create payment normally
                payment = Payment.objects.create(
                    company=request.company,
                    payment_type=PaymentType.RECEIVED,
                    customer=customer,
                    supplier=None,
                    sale=sale,
                    purchase=None,
                    payment_method=payment_method,
                    amount=payment_amount,
                    date=validated_data.get('date'),
                    reference_number=validated_data.get(
                        'reference_number', ''),
                    account_number=validated_data.get('account_number', ''),
                    account_holder_name=validated_data.get(
                        'account_holder_name', ''),
                    bank_name=validated_data.get('bank_name', ''),
                    branch_name=validated_data.get('branch_name', ''),
                    status=payment_status,
                    notes=validated_data.get('notes', ''),
                    created_by=user
                )

                if payment.status == 'completed' and payment.amount > 0:
                    LedgerService.create_payment_ledger_entry(
                        payment, request.company, customer, payment_type='received'
                    )
                    LedgerService.update_party_balance(
                        customer, request.company)

                serializer_output = PaymentSerializer(payment)
                return Response({
                    "message": "Customer payment created successfully",
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

    def put(self, request, pk=None):
        """Update customer payment"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Payment ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        payment = get_object_or_404(
            Payment.objects.filter(
                company=request.company,
                payment_type=PaymentType.RECEIVED
            ),
            pk=pk
        )

        # Delegate to parent view
        parent_view = PaymentAPIView()
        parent_view.request = request
        return parent_view.put(request, pk)

    def delete(self, request, pk=None):
        """Delete customer payment"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Payment ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        payment = get_object_or_404(
            Payment.objects.filter(
                company=request.company,
                payment_type=PaymentType.RECEIVED
            ),
            pk=pk
        )

        # Delegate to parent view
        parent_view = PaymentAPIView()
        parent_view.request = request
        return parent_view.delete(request, pk)


class SupplierPaymentAPIView(APIView):
    """Backward compatible view that filters to supplier payments only"""

    def get(self, request, pk=None):
        """Get supplier payments (payment_type='made')"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        if pk:
            payment = get_object_or_404(
                Payment.objects.filter(
                    company=request.company,
                    payment_type=PaymentType.MADE
                ).select_related('supplier', 'purchase', 'company', 'created_by'),
                pk=pk
            )
            serializer = PaymentSerializer(payment)
            return Response({
                "message": "Payment retrieved successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        # List supplier payments
        payments = Payment.objects.filter(
            company=request.company,
            payment_type=PaymentType.MADE
        ).select_related('supplier', 'purchase', 'company', 'created_by')

        # Apply filters
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            search_filter = (
                Q(supplier__name__icontains=search_query) |
                Q(reference_number__icontains=search_query) |
                Q(purchase__invoice_number__icontains=search_query)
            )
            try:
                search_id = int(search_query)
                search_filter |= Q(id=search_id)
            except (ValueError, TypeError):
                pass
            payments = payments.filter(search_filter)

        payment_method = request.query_params.get('payment_method', '').strip()
        if payment_method:
            payments = payments.filter(payment_method=payment_method)

        payment_status = request.query_params.get('status', '').strip()
        if payment_status:
            payments = payments.filter(status=payment_status)

        start_date = request.query_params.get('start_date', '').strip()
        end_date = request.query_params.get('end_date', '').strip()
        if start_date:
            payments = payments.filter(date__gte=start_date)
        if end_date:
            payments = payments.filter(date__lte=end_date)

        # Pagination
        page = request.query_params.get('page', None)
        page_size = request.query_params.get('page_size', None)

        if page and page_size:
            try:
                page = int(page)
                page_size = int(page_size)
                start = (page - 1) * page_size
                end = start + page_size
                total_count = payments.count()
                payments = payments.order_by('-date', '-created_at')[start:end]

                serializer = PaymentSerializer(payments, many=True)
                return Response({
                    "message": "Payments retrieved successfully",
                    "data": serializer.data,
                    "count": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 0
                }, status=status.HTTP_200_OK)
            except (ValueError, TypeError):
                pass

        # Return all if no pagination
        payments = payments.order_by('-date', '-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response({
            "message": "Payments retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        """Create supplier payment (automatically sets payment_type='made')"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        user = request.user if request.user.is_authenticated else None
        if not user:
            return Response({
                "error": "Authentication required"
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Add payment_type to the data
        data = request.data.copy()
        data['payment_type'] = PaymentType.MADE

        serializer = PaymentInputSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        try:
            with db_transaction.atomic():
                supplier = get_object_or_404(
                    Supplier.objects.filter(company=request.company),
                    id=validated_data['supplier']
                )

                purchase = None
                if validated_data.get('purchase'):
                    from purchase.models import Purchase
                    purchase = get_object_or_404(
                        Purchase.objects.filter(company=request.company),
                        id=validated_data['purchase']
                    )

                payment_status = validated_data.get('status', 'completed')
                payment_method = validated_data.get('payment_method', PaymentMethod.CASH)
                payment_amount = validated_data['amount']
                payment_date = validated_data.get('date') or timezone.now().date()
                
                # Apply FIFO for cash payments that are completed
                if (payment_method == PaymentMethod.CASH and 
                    payment_status == PayStatus.COMPLETED and 
                    payment_amount > 0):
                    
                    # Apply payment using FIFO
                    applied_payments = PaymentFIFOService.apply_payment_to_invoices(
                        payment_amount=payment_amount,
                        party=supplier,
                        invoice_type='purchase',
                        company=request.company,
                        user=user,
                        specific_invoice=purchase,
                        payment_date=payment_date
                    )
                    
                    # Return response with FIFO information
                    created_payments = Payment.objects.filter(
                        company=request.company,
                        payment_type=PaymentType.MADE,
                        supplier=supplier,
                        payment_method=payment_method,
                        date=payment_date,
                        created_by=user
                    ).order_by('-created_at')[:len(applied_payments)]
                    
                    first_payment = created_payments.first() if created_payments.exists() else None
                    serializer_output = PaymentSerializer(first_payment) if first_payment else None
                    
                    return Response({
                        "message": "Supplier payment created successfully (FIFO applied)",
                        "data": serializer_output.data if serializer_output else None,
                        "applied_to_invoices": [
                            {
                                "invoice_id": inv.id,
                                "invoice_number": inv.invoice_number or str(inv.id),
                                "applied_amount": float(applied_amount)
                            }
                            for inv, applied_amount in applied_payments
                        ]
                    }, status=status.HTTP_201_CREATED)

                # For non-cash or non-completed payments, create payment normally
                payment = Payment.objects.create(
                    company=request.company,
                    payment_type=PaymentType.MADE,
                    customer=None,
                    supplier=supplier,
                    sale=None,
                    purchase=purchase,
                    payment_method=payment_method,
                    amount=payment_amount,
                    date=validated_data.get('date'),
                    reference_number=validated_data.get(
                        'reference_number', ''),
                    account_number=validated_data.get('account_number', ''),
                    account_holder_name=validated_data.get(
                        'account_holder_name', ''),
                    bank_name=validated_data.get('bank_name', ''),
                    branch_name=validated_data.get('branch_name', ''),
                    status=payment_status,
                    notes=validated_data.get('notes', ''),
                    created_by=user
                )

                if payment.status == 'completed' and payment.amount > 0:
                    LedgerService.create_payment_ledger_entry(
                        payment, request.company, supplier, payment_type='made'
                    )
                    LedgerService.update_party_balance(
                        supplier, request.company)

                serializer_output = PaymentSerializer(payment)
                return Response({
                    "message": "Supplier payment created successfully",
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

    def put(self, request, pk=None):
        """Update supplier payment"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Payment ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        payment = get_object_or_404(
            Payment.objects.filter(
                company=request.company,
                payment_type=PaymentType.MADE
            ),
            pk=pk
        )

        # Delegate to parent view
        parent_view = PaymentAPIView()
        parent_view.request = request
        return parent_view.put(request, pk)

    def delete(self, request, pk=None):
        """Delete supplier payment"""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        if not pk:
            return Response({
                "error": "Payment ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        payment = get_object_or_404(
            Payment.objects.filter(
                company=request.company,
                payment_type=PaymentType.MADE
            ),
            pk=pk
        )

        # Delegate to parent view
        parent_view = PaymentAPIView()
        parent_view.request = request
        return parent_view.delete(request, pk)
