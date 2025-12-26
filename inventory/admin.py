from django.contrib import admin
from .models import Stock, StockTransaction


admin.site.register([
    Stock,
    StockTransaction
])
