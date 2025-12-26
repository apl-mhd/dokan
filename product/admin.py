from django.contrib import admin
from .models import UnitCategory, Unit, Category, Product

admin.site.register([
    UnitCategory,
    Unit,
    Category,
    Product,
])
