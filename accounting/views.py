from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from .models import Ledger, TransactionType
from .serializers import LedgerSerializer


class LedgerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for ledger entries.
    Ledger entries are created automatically by the system.
    Company-filtered: only shows ledger entries belonging to user's company.
    """
    serializer_class = LedgerSerializer
    
    def get_queryset(self):
        """Filter ledger entries by company and apply search/filters"""
        queryset = Ledger.objects.select_related(
            'party', 'company', 'content_type'
        ).all()
        
        # Filter by company if middleware provides it
        if hasattr(self.request, 'company') and self.request.company:
            queryset = queryset.filter(company=self.request.company)
        
        # Search filter - search in party name, txn_id, description
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(party__name__icontains=search) |
                Q(txn_id__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Transaction type filter
        txn_type = self.request.query_params.get('txn_type', None)
        if txn_type:
            queryset = queryset.filter(txn_type=txn_type)
        
        # Party filter
        party = self.request.query_params.get('party', None)
        if party:
            queryset = queryset.filter(party_id=party)
        
        # Date range filters
        date_from = self.request.query_params.get('date_from', None)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to', None)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        return queryset.order_by('-date', '-created_at')
    
    def list(self, request, *args, **kwargs):
        """Custom list response format"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "message": "Ledger entries retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    
    def retrieve(self, request, *args, **kwargs):
        """Custom retrieve response format"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "message": "Ledger entry retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
