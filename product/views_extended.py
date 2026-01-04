from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Category, Unit, UnitCategory
from .serializers import (
    CategorySerializer,
    UnitSerializer,
    UnitCategorySerializer
)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Category CRUD operations.
    Company-filtered: only shows categories belonging to user's company.
    """
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        """Filter categories by company if available"""
        from .models import Category
        queryset = Category.objects.select_related('company').all()

        if hasattr(self.request, 'company') and self.request.company:
            queryset = queryset.filter(company=self.request.company)

        return queryset.order_by('name')

    def perform_create(self, serializer):
        """Auto-set company when creating category"""
        company = getattr(self.request, 'company', None)
        if company:
            serializer.save(company=company)
        else:
            serializer.save()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "message": "Categories retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "message": "Category retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({
            "message": "Category created successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            "message": "Category updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            "message": "Category deleted successfully"
        }, status=status.HTTP_204_NO_CONTENT)


class UnitCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for UnitCategory CRUD operations.
    Company-filtered: only shows unit categories belonging to user's company.
    """
    serializer_class = UnitCategorySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        """Filter unit categories by company if available"""
        queryset = UnitCategory.objects.select_related('company').all()

        if hasattr(self.request, 'company') and self.request.company:
            queryset = queryset.filter(company=self.request.company)

        return queryset.order_by('name')

    def perform_create(self, serializer):
        """Auto-set company when creating unit category"""
        company = getattr(self.request, 'company', None)
        if company:
            serializer.save(company=company)
        else:
            serializer.save()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "message": "Unit categories retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "message": "Unit category retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({
            "message": "Unit category created successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            "message": "Unit category updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            "message": "Unit category deleted successfully"
        }, status=status.HTTP_204_NO_CONTENT)


class UnitManagementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Unit CRUD operations.
    Company-filtered: only shows units belonging to user's company.
    """
    serializer_class = UnitSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        """Filter units by company if available"""
        queryset = Unit.objects.select_related(
            'company', 'unit_category').all()

        if hasattr(self.request, 'company') and self.request.company:
            queryset = queryset.filter(company=self.request.company)

        return queryset.order_by('unit_category__name', 'name')

    def perform_create(self, serializer):
        """Auto-set company when creating unit"""
        company = getattr(self.request, 'company', None)
        if company:
            serializer.save(company=company)
        else:
            serializer.save()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "message": "Units retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "message": "Unit retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({
            "message": "Unit created successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            "message": "Unit updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            "message": "Unit deleted successfully"
        }, status=status.HTTP_204_NO_CONTENT)
