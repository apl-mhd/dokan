
from core.dashboard_views import DashboardStatsAPIView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.urls import re_path, path, include
from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Dokan API",
        default_version='v1',
        description="API documentation for Dokan project",
        contact=openapi.Contact(email="youremail@example.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)


urlpatterns = [
    path('admin/', admin.site.urls),

    # Main APIs
    path('api/purchases/', include('purchase.urls')),
    path('api/sales/', include('sale.urls')),
    path('api/products/', include('product.urls')),
    path('api/suppliers/', include('supplier.urls')),
    path('api/customers/', include('customer.urls')),
    path('api/warehouses/', include('warehouse.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/accounting/', include('accounting.urls')),
    path('api/payments/', include('payment.urls')),
    path('api/expenses/', include('expense.urls')),

    # Dashboard
    path('api/dashboard/stats/', DashboardStatsAPIView.as_view(),
         name='dashboard-stats'),

    # Authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # API Documentation
    re_path(r'^swagger(?P<format>\.json|\.yaml)$',
            schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0),
         name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0),
         name='schema-redoc'),
]
