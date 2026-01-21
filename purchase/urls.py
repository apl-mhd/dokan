from django.urls import path
from . import views

urlpatterns = [
    # Test endpoint
    path('test/', views.test, name='purchase-test'),
    
    # Company-aware Purchase CRUD endpoints
    path('', views.PurchaseAPIView.as_view(), name='purchase-list-create'),
    path('<int:pk>/', views.PurchaseAPIView.as_view(), name='purchase-detail'),
    path('<int:pk>/take-payment/', views.PurchaseTakePaymentAPIView.as_view(), name='purchase-take-payment'),
    
    # PDF Invoice generation
    path('<int:pk>/pdf/', views.PurchaseInvoicePDFView.as_view(), name='purchase-invoice-pdf'),
    
    # Purchase Return endpoints
    path('returns/', views.PurchaseReturnAPIView.as_view(), name='purchase-return-list-create'),
    path('returns/<int:pk>/', views.PurchaseReturnAPIView.as_view(), name='purchase-return-detail'),
    
    # Purchase Return Actions
    path('returns/<int:pk>/complete/', views.PurchaseReturnCompleteAPIView.as_view(), name='purchase-return-complete'),
    path('returns/<int:pk>/cancel/', views.PurchaseReturnCancelAPIView.as_view(), name='purchase-return-cancel'),
    
    # Get returnable items for a purchase
    path('<int:purchase_id>/returnable-items/', views.PurchaseReturnableItemsAPIView.as_view(), name='purchase-returnable-items'),
]
