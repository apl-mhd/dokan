from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
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
            'product', 'product__base_unit', 'warehouse', 'company'
        ).all()
        
        # Filter by company if middleware provides it
        if hasattr(self.request, 'company') and self.request.company:
            queryset = queryset.filter(company=self.request.company)
        
        return queryset.order_by('product__name', 'warehouse__name')
    
    def list(self, request, *args, **kwargs):
        """Custom list response format with search and filters"""
        queryset = self.get_queryset()
        
        # Apply search filter
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(product__name__icontains=search_query) |
                Q(warehouse__name__icontains=search_query)
            )
        
        # Apply warehouse filter
        warehouse_id = request.query_params.get('warehouse', '').strip()
        if warehouse_id:
            try:
                queryset = queryset.filter(warehouse_id=int(warehouse_id))
            except (ValueError, TypeError):
                pass
        
        # Apply product filter
        product_id = request.query_params.get('product', '').strip()
        if product_id:
            try:
                queryset = queryset.filter(product_id=int(product_id))
            except (ValueError, TypeError):
                pass
        
        # Apply stock level filter (low/medium/high)
        stock_level = request.query_params.get('stock_level', '').strip()
        if stock_level:
            if stock_level == 'low':
                queryset = queryset.filter(quantity__lte=10)
            elif stock_level == 'medium':
                queryset = queryset.filter(quantity__gt=10, quantity__lte=100)
            elif stock_level == 'high':
                queryset = queryset.filter(quantity__gt=100)
        
        # Apply pagination
        page = request.query_params.get('page', None)
        page_size = request.query_params.get('page_size', None)
        
        if page and page_size:
            try:
                page = int(page)
                page_size = int(page_size)
                start = (page - 1) * page_size
                end = start + page_size
                total_count = queryset.count()
                queryset = queryset[start:end]
                
                serializer = self.get_serializer(queryset, many=True)
                return Response({
                    "message": "Stocks retrieved successfully",
                    "data": serializer.data,
                    "count": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 0
                }, status=status.HTTP_200_OK)
            except (ValueError, TypeError):
                pass
        
        # Return all if no pagination
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
            'product', 'product__base_unit', 'stock', 'stock__warehouse', 'unit', 'company'
        ).all()
        
        # Filter by company if middleware provides it
        if hasattr(self.request, 'company') and self.request.company:
            queryset = queryset.filter(company=self.request.company)
        
        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """Custom list response format with search and filters"""
        queryset = self.get_queryset()
        
        # Apply search filter
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(product__name__icontains=search_query) |
                Q(stock__warehouse__name__icontains=search_query) |
                Q(transaction_type__icontains=search_query) |
                Q(note__icontains=search_query)
            )
        
        # Apply transaction type filter
        transaction_type = request.query_params.get('transaction_type', '').strip()
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Apply direction filter (in/out)
        direction = request.query_params.get('direction', '').strip()
        if direction:
            queryset = queryset.filter(direction=direction)
        
        # Apply product filter
        product_id = request.query_params.get('product', '').strip()
        if product_id:
            try:
                queryset = queryset.filter(product_id=int(product_id))
            except (ValueError, TypeError):
                pass
        
        # Apply warehouse filter
        warehouse_id = request.query_params.get('warehouse', '').strip()
        if warehouse_id:
            try:
                queryset = queryset.filter(stock__warehouse_id=int(warehouse_id))
            except (ValueError, TypeError):
                pass
        
        # Apply pagination
        page = request.query_params.get('page', None)
        page_size = request.query_params.get('page_size', None)
        
        if page and page_size:
            try:
                page = int(page)
                page_size = int(page_size)
                start = (page - 1) * page_size
                end = start + page_size
                total_count = queryset.count()
                queryset = queryset[start:end]
                
                serializer = self.get_serializer(queryset, many=True)
                return Response({
                    "message": "Stock transactions retrieved successfully",
                    "data": serializer.data,
                    "count": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 0
                }, status=status.HTTP_200_OK)
            except (ValueError, TypeError):
                pass
        
        # Return all if no pagination
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
