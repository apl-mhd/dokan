from django.contrib import admin
from .models import UnitCategory,Unit, Category, Product, StockLedger, Stock, Warehouse

# Register your models here.


admin.site.register([
    UnitCategory,
    Unit,
    Category,
    Product,
    StockLedger,
    Stock,
    Warehouse
])
