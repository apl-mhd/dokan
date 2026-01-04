from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'stocks', views.StockViewSet, basename='stock')
router.register(r'transactions', views.StockTransactionViewSet, basename='stock-transaction')

urlpatterns = router.urls

