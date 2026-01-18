from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'ledgers', views.LedgerViewSet, basename='ledger')

urlpatterns = router.urls
