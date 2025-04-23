from django.contrib import admin
from .models import Unit, Category, Product

# Register your models here.


admin.site.register([
    Unit,
    Category,
    Product,
])
