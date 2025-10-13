from django.urls import path, include
from . import views


urlpatterns = [
    path('', views.SaleListAPIView.as_view(), name='sale-list'),
    path('<int:pk>/', views.SaleAPIView.as_view(), name='sale'),
]
