from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db.models import Q
from .models import ExpenseCategory, Expense
from .serializers import ExpenseCategorySerializer, ExpenseSerializer


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    """CRUD for expense categories. Company-filtered."""
    serializer_class = ExpenseCategorySerializer

    def get_queryset(self):
        if not (hasattr(self.request, 'company') and self.request.company):
            return ExpenseCategory.objects.none()
        return ExpenseCategory.objects.filter(company=self.request.company).order_by('name')

    def perform_create(self, serializer):
        if not (hasattr(self.request, 'company') and self.request.company):
            raise ValidationError({'company': 'Company context is required.'})
        serializer.save(company=self.request.company)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(name__icontains=search)
        is_active = request.query_params.get('is_active', '').strip()
        if is_active != '':
            if is_active.lower() in ('true', '1', 'yes'):
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() in ('false', '0', 'no'):
                queryset = queryset.filter(is_active=False)

        page = request.query_params.get('page')
        page_size = request.query_params.get('page_size')
        if page and page_size:
            try:
                page, page_size = int(page), int(page_size)
                start = (page - 1) * page_size
                end = start + page_size
                total = queryset.count()
                queryset = queryset[start:end]
                serializer = self.get_serializer(queryset, many=True)
                return Response({
                    'message': 'Categories retrieved.',
                    'data': serializer.data,
                    'count': total,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total + page_size - 1) // page_size if total else 0
                })
            except (ValueError, TypeError):
                pass

        serializer = self.get_serializer(queryset, many=True)
        return Response({'message': 'Categories retrieved.', 'data': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({'message': 'Category retrieved.', 'data': serializer.data})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({'message': 'Category created.', 'data': serializer.data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'message': 'Category updated.', 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.expenses.exists():
            return Response(
                {'error': 'Cannot delete category that has expenses. Remove or reassign expenses first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExpenseViewSet(viewsets.ModelViewSet):
    """CRUD for expenses. Company-filtered. Entry by category."""
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        if not (hasattr(self.request, 'company') and self.request.company):
            return Expense.objects.none()
        return (
            Expense.objects
            .filter(company=self.request.company)
            .select_related('category', 'created_by')
            .order_by('-date', '-created_at')
        )

    def perform_create(self, serializer):
        if not (hasattr(self.request, 'company') and self.request.company):
            raise ValidationError({'company': 'Company context is required.'})
        serializer.save(company=self.request.company, created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        category_id = request.query_params.get('category', '').strip()
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        date_from = request.query_params.get('date_from', '').strip()
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        date_to = request.query_params.get('date_to', '').strip()
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(description__icontains=search) | Q(category__name__icontains=search)
            )

        page = request.query_params.get('page')
        page_size = request.query_params.get('page_size')
        if page and page_size:
            try:
                page, page_size = int(page), int(page_size)
                start = (page - 1) * page_size
                end = start + page_size
                total = queryset.count()
                queryset = queryset[start:end]
                serializer = self.get_serializer(queryset, many=True)
                return Response({
                    'message': 'Expenses retrieved.',
                    'data': serializer.data,
                    'count': total,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total + page_size - 1) // page_size if total else 0
                })
            except (ValueError, TypeError):
                pass

        serializer = self.get_serializer(queryset, many=True)
        return Response({'message': 'Expenses retrieved.', 'data': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({'message': 'Expense retrieved.', 'data': serializer.data})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({'message': 'Expense created.', 'data': serializer.data}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'message': 'Expense updated.', 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        self.perform_destroy(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)
