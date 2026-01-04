from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from .models import Stock, StockTransaction
from .serializers import StockSerializer, StockTransactionSerializer


class StockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for stock.
    Stock is managed through purchases/sales, not directly.
    Company-filtered: only shows stock belonging to user's company.
    """
    serializer_class = StockSerializer
    
    def get_queryset(self):
        """Filter stock by company if available"""
        queryset = Stock.objects.select_related(
            'product', 'warehouse', 'company'
        ).all()
        
        # Filter by company if middleware provides it
        if hasattr(self.request, 'company') and self.request.company:
            queryset = queryset.filter(company=self.request.company)
        
        return queryset.order_by('product__name', 'warehouse__name')
    
    def list(self, request, *args, **kwargs):
        """Custom list response format"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "message": "Stocks retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    
    def retrieve(self, request, *args, **kwargs):
        """Custom retrieve response format"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "message": "Stock retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class StockTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for stock transactions.
    Transactions are created automatically by the system.
    Company-filtered: only shows transactions belonging to user's company.
    """
    serializer_class = StockTransactionSerializer
    
    def get_queryset(self):
        """Filter transactions by company if available"""
        queryset = StockTransaction.objects.select_related(
            'product', 'stock', 'stock__warehouse', 'unit', 'company'
        ).all()
        
        # Filter by company if middleware provides it
        if hasattr(self.request, 'company') and self.request.company:
            queryset = queryset.filter(company=self.request.company)
        
        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """Custom list response format"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "message": "Stock transactions retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    
    def retrieve(self, request, *args, **kwargs):
        """Custom retrieve response format"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "message": "Stock transaction retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
