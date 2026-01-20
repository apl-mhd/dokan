from django.urls import path
from . import views

urlpatterns = [
    # Unified Payment API (recommended)
    path('', views.PaymentAPIView.as_view(), name='payment-list-create'),
    path('<int:pk>/', views.PaymentAPIView.as_view(), name='payment-detail'),

    # Backward compatibility for frontend (auto-filters by payment_type)
    path('customer/', views.CustomerPaymentAPIView.as_view(), name='customer-payment-list-create'),
    path('customer/<int:pk>/', views.CustomerPaymentAPIView.as_view(), name='customer-payment-detail'),
    path('supplier/', views.SupplierPaymentAPIView.as_view(), name='supplier-payment-list-create'),
    path('supplier/<int:pk>/', views.SupplierPaymentAPIView.as_view(), name='supplier-payment-detail'),
]
