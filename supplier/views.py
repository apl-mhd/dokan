from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from .models import Supplier
from .serializer import SupplierSerializer
from accounting.services.ledger_service import LedgerService


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

    def list(self, request, *args, **kwargs):
        """Custom list response format"""
        queryset = self.filter_queryset(self.get_queryset())
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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({
            "message": "Supplier created successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Custom update response format"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

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
