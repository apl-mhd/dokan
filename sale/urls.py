from django.urls import path
from . import views

urlpatterns = [
    # Company-aware Sale CRUD endpoints
    path('', views.SaleAPIView.as_view(), name='sale-list-create'),
    path('<int:pk>/', views.SaleAPIView.as_view(), name='sale-detail'),
    path('<int:pk>/take-payment/', views.SaleTakePaymentAPIView.as_view(), name='sale-take-payment'),
    
    # PDF Invoice generation
    path('<int:pk>/pdf/', views.SaleInvoicePDFView.as_view(), name='sale-invoice-pdf'),
    
    # Sale Returns CRUD endpoints
    path('returns/', views.SaleReturnAPIView.as_view(), name='sale-return-list-create'),
    path('returns/<int:pk>/', views.SaleReturnAPIView.as_view(), name='sale-return-detail'),
    
    # Sale Return Actions
    path('returns/<int:pk>/complete/', views.SaleReturnCompleteAPIView.as_view(), name='sale-return-complete'),
    path('returns/<int:pk>/cancel/', views.SaleReturnCancelAPIView.as_view(), name='sale-return-cancel'),
    
    # Get returnable items for a sale
    path('<int:sale_id>/returnable-items/', views.SaleReturnableItemsAPIView.as_view(), name='sale-returnable-items'),
]
