from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'', views.PurchaseViewSet, basename='purchasea')



urlpatterns = [
    # path('', views.PurchaseAPIView.as_view(), name='purchase'),
    # path('<int:pk>/', views.PurchaseAPIView.as_view(), name='purchase'),
    path('test', views.test, name='test'),
    path('', include(router.urls)),
] 

