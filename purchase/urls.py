from django.urls import path, include
from . import views


urlpatterns = [
    path('', views.PurchaseAPIView.as_view(), name='purchase'),
    path('<int:pk>/', views.PurchaseAPIView.as_view(), name='purchase'),
    path('test', views.test, name='test'),
]
