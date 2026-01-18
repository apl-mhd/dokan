from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from .models import Customer
from .serializer import CustomerSerializer
from accounting.services.ledger_service import LedgerService


class CustomerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Customer CRUD operations.
    Company-filtered: only shows customers belonging to user's company.
    """
    serializer_class = CustomerSerializer

    def get_queryset(self):
        """Filter customers by company if available"""
        queryset = Customer.objects.select_related('company').all()

        # Filter by company if middleware provides it
        if hasattr(self.request, 'company') and self.request.company:
            queryset = queryset.filter(company=self.request.company)

        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Auto-set company when creating customer"""
        company = getattr(self.request, 'company', None)
        if not company:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                {'company': 'Company context is required. Please ensure you are associated with a company.'})
        customer = serializer.save(company=company, is_customer=True)

        # Create opening balance ledger entry if opening_balance > 0
        opening_balance = serializer.validated_data.get(
            'opening_balance', 0) or customer.opening_balance
        if opening_balance:
            LedgerService.create_or_update_opening_balance_entry(
                customer, company, opening_balance)
            LedgerService.update_party_balance(customer, company)

    def list(self, request, *args, **kwargs):
        """Custom list response format"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "message": "Customers retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        """Custom retrieve response format"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "message": "Customer retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        """Custom create response format"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({
            "message": "Customer created successfully",
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
        customer = instance

        # Update opening balance ledger entry if opening_balance is set
        company = getattr(request, 'company', None)
        if company:
            opening_balance = serializer.validated_data.get('opening_balance')
            if opening_balance is not None:
                # Use updated opening_balance from instance
                LedgerService.create_or_update_opening_balance_entry(
                    customer, company, customer.opening_balance)
                LedgerService.update_party_balance(customer, company)

        return Response({
            "message": "Customer updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """Custom delete response format"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            "message": "Customer deleted successfully"
        }, status=status.HTTP_204_NO_CONTENT)
