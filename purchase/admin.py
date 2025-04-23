from django.contrib import admin
from .models import Purchase, PurchaseItem
# Register your models here.

admin.site.register([
    Purchase,
    PurchaseItem,
])
