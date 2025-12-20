from django.urls import re_path, path, include
from django.contrib import admin
from rest_framework.routers import DefaultRouter
from . import views


router = DefaultRouter()
router.register(r'', views.SupplierViewSet, basename='supplier')




urlpatterns = [


     
]

urlpatterns += router.urls
