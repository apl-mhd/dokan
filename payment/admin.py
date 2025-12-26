from django.contrib import admin
from .models import CustomerPayment, SupplierPayment

# Register your models here.

admin.site.register([
    CustomerPayment,
    SupplierPayment
])
