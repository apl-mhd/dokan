from django.urls import path
from . import views

urlpatterns = [
    # Company-aware Sale CRUD endpoints
    path('', views.SaleAPIView.as_view(), name='sale-list-create'),
    path('<int:pk>/', views.SaleAPIView.as_view(), name='sale-detail'),
]
