from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'', views.PurchaseViewSet, basename='purchase')

urlpatterns = [
    path('test', views.test, name='test'),
    path('', views.PurchaseAPIView.as_view(), name='purchase-list'),
    path('<int:pk>/', views.PurchaseAPIView.as_view(), name='purchase-detail'),
    path('viewset/', include(router.urls)),
] 

