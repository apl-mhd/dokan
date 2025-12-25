from django.urls import path, include
from rest_framework import routers
from .views import ProductUnitListAPIView, ProductViewSet, ProductAPIView

router = routers.DefaultRouter()
router.register(r'', ProductViewSet)
# router.register(r'product-unit', ProductUnitListAPIView, basename='product-unit')

urlpatterns = [
     path('', include(router.urls)),
     path('product/<int:product_id>/', ProductAPIView.as_view(), name='product'),
     path('product-units/<int:product_id>/', ProductUnitListAPIView.as_view(), name='product-unit'),
]


