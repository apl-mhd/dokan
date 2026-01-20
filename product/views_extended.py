from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Category, Unit, UnitCategory
from django.db.models import Q
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

        # Search by category name
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(Q(name__icontains=search_query))

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
                    "message": "Unit categories retrieved successfully",
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

        # Search by unit name or category name
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(unit_category__name__icontains=search_query)
            )

        # Filter by unit_category id
        unit_category_id = request.query_params.get('unit_category', '').strip()
        if unit_category_id:
            try:
                queryset = queryset.filter(unit_category_id=int(unit_category_id))
            except (ValueError, TypeError):
                pass

        # Filter base/derived
        is_base_unit = request.query_params.get('is_base_unit', '').strip()
        if is_base_unit != '':
            if is_base_unit.lower() in ['true', '1', 'yes']:
                queryset = queryset.filter(is_base_unit=True)
            elif is_base_unit.lower() in ['false', '0', 'no']:
                queryset = queryset.filter(is_base_unit=False)

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
                    "message": "Units retrieved successfully",
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
