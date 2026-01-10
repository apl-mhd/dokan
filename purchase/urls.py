from django.urls import path
from . import views

urlpatterns = [
    # Test endpoint
    path('test/', views.test, name='purchase-test'),
    
    # Company-aware Purchase CRUD endpoints
    path('', views.PurchaseAPIView.as_view(), name='purchase-list-create'),
    path('<int:pk>/', views.PurchaseAPIView.as_view(), name='purchase-detail'),
    
    # PDF Invoice generation
    path('<int:pk>/pdf/', views.PurchaseInvoicePDFView.as_view(), name='purchase-invoice-pdf'),
]
