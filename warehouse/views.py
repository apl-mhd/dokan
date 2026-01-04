from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from .models import Warehouse
from .serializers import WarehouseSerializer


class WarehouseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Warehouse CRUD operations.
    Company-filtered: only shows warehouses belonging to user's company.
    """
    serializer_class = WarehouseSerializer
    
    def get_queryset(self):
        """Filter warehouses by company if available"""
        queryset = Warehouse.objects.select_related('company').all()
        
        # Filter by company if middleware provides it
        if hasattr(self.request, 'company') and self.request.company:
            queryset = queryset.filter(company=self.request.company)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Auto-set company when creating warehouse"""
        company = getattr(self.request, 'company', None)
        if company:
            serializer.save(company=company)
        else:
            serializer.save()
    
    def list(self, request, *args, **kwargs):
        """Custom list response format"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "message": "Warehouses retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    
    def retrieve(self, request, *args, **kwargs):
        """Custom retrieve response format"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "message": "Warehouse retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    
    def create(self, request, *args, **kwargs):
        """Custom create response format"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({
            "message": "Warehouse created successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Custom update response format"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            "message": "Warehouse updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        """Custom delete response format"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            "message": "Warehouse deleted successfully"
        }, status=status.HTTP_204_NO_CONTENT)
