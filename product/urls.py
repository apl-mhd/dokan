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

# router = routers.DefaultRouter()
# router.register(r'', ProductViewSet, basename='product')
# router.register(r'units', UnitViewSet, basename='unit')

urlpatterns = [
    path('test/', TestApi.as_view(), name='test-api'),
  #  path('', include(router.urls)),
    path('list/', ProductAPIView.as_view(), name='product-list'),
    path('<int:product_id>/', ProductAPIView.as_view(), name='product-detail'),
    path('<int:product_id>/units/',
         ProductUnitListAPIView.as_view(), name='product-units'),
    path('stock-check/', StockCheckAPIView.as_view(), name='stock-check'),
]
