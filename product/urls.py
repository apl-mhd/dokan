from django.urls import path, include
from rest_framework import routers
from .views import (
    ProductUnitListAPIView,
    ProductViewSet,
    ProductAPIView,
    UnitViewSet,
    StockCheckAPIView,
    TestApi
)
from .views_extended import (
    CategoryViewSet,
    UnitCategoryViewSet,
    UnitManagementViewSet
)

# Create router for ViewSets
router = routers.DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'unit-categories', UnitCategoryViewSet,
                basename='unit-category')
router.register(r'units', UnitManagementViewSet, basename='unit-management')

urlpatterns = [
    path('test/', TestApi.as_view(), name='test-api'),

    # Product endpoints
    path('list/', ProductAPIView.as_view(), name='product-list'),
    path('<int:product_id>/', ProductAPIView.as_view(), name='product-detail'),
    path('<int:product_id>/units/',
         ProductUnitListAPIView.as_view(), name='product-units'),
    path('stock-check/', StockCheckAPIView.as_view(), name='stock-check'),

    # Category, Unit, UnitCategory ViewSets
    path('', include(router.urls)),
]
