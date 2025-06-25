from django.urls import path, include
from . import views


urlpatterns = [
    path('', views.SaleAPIView.as_view(), name='sale'),
    path('<int:pk>/', views.SaleAPIView.as_view(), name='sale'),
]
