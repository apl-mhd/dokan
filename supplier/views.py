from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from django.utils.dateparse import parse_date
from .models import Supplier
from .serializer import SupplierSerializer
from accounting.services.ledger_service import LedgerService
from django.db.models import Q


class SupplierViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Supplier CRUD operations.
    Company-filtered: only shows suppliers belonging to user's company.
    """
    serializer_class = SupplierSerializer

    def get_queryset(self):
        """Filter suppliers by company if available"""
        queryset = Supplier.objects.select_related('company').all()

        # Filter by company if middleware provides it
        if hasattr(self.request, 'company') and self.request.company:
            queryset = queryset.filter(company=self.request.company)

        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Auto-set company when creating supplier"""
        try:
            company = getattr(self.request, 'company', None)
            if not company:
                from rest_framework.exceptions import ValidationError
                raise ValidationError(
                    {'company': 'Company context is required. Please ensure you are associated with a company.'})
            supplier = serializer.save(company=company, is_supplier=True)

            # Create opening balance ledger entry if opening_balance > 0
            opening_balance = serializer.validated_data.get(
                'opening_balance', 0) or supplier.opening_balance
            if opening_balance:
                LedgerService.create_or_update_opening_balance_entry(
                    supplier, company, opening_balance)
                LedgerService.update_party_balance(supplier, company)
        except Exception as e:
            # Handle IntegrityError for unique constraint violations
            from django.db import IntegrityError
            from rest_framework.exceptions import ValidationError as DRFValidationError
            
            # If it's already a ValidationError, let it bubble up
            if isinstance(e, DRFValidationError):
                raise
            
            # Convert IntegrityError to ValidationError
            if isinstance(e, IntegrityError):
                if 'phone' in str(e) or 'unique' in str(e).lower():
                    raise DRFValidationError({
                        'phone': 'This phone number is already registered. Phone numbers must be unique within your company.'
                    })
            
            raise

    def list(self, request, *args, **kwargs):
        """Custom list response format with search, filters, pagination"""
        queryset = self.filter_queryset(self.get_queryset())

        # Search (name/email/phone)
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(phone__icontains=search_query)
            )

        # Status filter
        is_active = request.query_params.get('is_active', '').strip()
        if is_active != '':
            if is_active.lower() in ['true', '1', 'yes']:
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() in ['false', '0', 'no']:
                queryset = queryset.filter(is_active=False)

        # Pagination
        page = request.query_params.get('page', None)
        page_size = request.query_params.get('page_size', None)

        if page and page_size:
            try:
                page = int(page)
                page_size = int(page_size)
                start = (page - 1) * page_size
                end = start + page_size
                total_count = queryset.count()
                page_qs = queryset[start:end]
                serializer = self.get_serializer(page_qs, many=True)
                return Response({
                    "message": "Suppliers retrieved successfully",
                    "data": serializer.data,
                    "count": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 0
                }, status=status.HTTP_200_OK)
            except (ValueError, TypeError):
                pass

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "message": "Suppliers retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        """Custom retrieve response format"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "message": "Supplier retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        """Custom create response format"""
        try:
            serializer = self.get_serializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response({
                "message": "Supplier created successfully",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            # Handle IntegrityError for unique constraint violations
            from django.db import IntegrityError
            if isinstance(e, IntegrityError) and 'phone' in str(e):
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    'phone': 'This phone number is already registered. Phone numbers must be unique within your company.'
                })
            raise

    def update(self, request, *args, **kwargs):
        """Custom update response format"""
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(
                instance, data=request.data, partial=partial, context={'request': request})
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
        except Exception as e:
            # Handle IntegrityError for unique constraint violations
            from django.db import IntegrityError
            from rest_framework.exceptions import ValidationError as DRFValidationError
            
            # If it's already a ValidationError, let it bubble up
            if isinstance(e, DRFValidationError):
                raise
            
            # Convert IntegrityError to ValidationError
            if isinstance(e, IntegrityError):
                if 'phone' in str(e) or 'unique' in str(e).lower():
                    raise DRFValidationError({
                        'phone': 'This phone number is already registered. Phone numbers must be unique within your company.'
                    })
            
            raise

        # Refresh instance to get updated opening_balance
        instance.refresh_from_db()
        supplier = instance

        # Update opening balance ledger entry if opening_balance is set
        company = getattr(request, 'company', None)
        if company:
            opening_balance = serializer.validated_data.get('opening_balance')
            if opening_balance is not None:
                # Use updated opening_balance from instance
                LedgerService.create_or_update_opening_balance_entry(
                    supplier, company, supplier.opening_balance)
                LedgerService.update_party_balance(supplier, company)

        return Response({
            "message": "Supplier updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """Custom delete response format"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            "message": "Supplier deleted successfully"
        }, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='adjust-balance')
    def adjust_balance(self, request, pk=None):
        """Adjust supplier balance. Creates ledger entry and updates party balance."""
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
            }, status=status.HTTP_403_FORBIDDEN)

        supplier = self.get_object()
        amount = request.data.get('amount')
        description = request.data.get('description', '').strip()
        adjustment_date = request.data.get('date')

        if amount is None:
            return Response({
                "error": "Validation error",
                "details": {"amount": ["Amount is required"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(amount))
        except (TypeError, ValueError):
            return Response({
                "error": "Validation error",
                "details": {"amount": ["Invalid amount"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        if amount == 0:
            return Response({
                "error": "Validation error",
                "details": {"amount": ["Amount cannot be zero"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        adj_date = parse_date(adjustment_date) if adjustment_date else None

        try:
            LedgerService.create_balance_adjustment_entry(
                party=supplier,
                company=request.company,
                amount=amount,
                description=description or f"Balance Adjustment - Supplier {supplier.name}",
                adjustment_date=adj_date
            )
        except ValueError as e:
            return Response({
                "error": "Validation error",
                "details": {"amount": [str(e)]}
            }, status=status.HTTP_400_BAD_REQUEST)

        supplier.refresh_from_db()
        serializer = self.get_serializer(supplier)
        return Response({
            "message": "Balance adjusted successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
