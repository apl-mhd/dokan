from django.contrib import admin
from .models import Customer
from sale.models import Sale
from sale.models import SaleItem
# Register your models here.


admin.site.register([
    Customer
])


# class SaleItemInline(admin.TabularInline):
#     model = Sale
#     extra = 1

# @admin.register(Customer)
# class CustomerAdmin(admin.ModelAdmin):
#     list_display = ['name', 'email', 'phone', 'address', 'is_active']
#     search_fields = [ 'email', 'phone']
#     list_filter = ('is_active', 'created_at')


#     actions = ['make_active', 'make_inactive']

#     inlines = [SaleItemInline]

#     @admin.action(description='Mark selected customers as active')
#     def make_active(self, request, queryset):
#         queryset.update(is_active=True)

#     @admin.action(description='Mark selected customers as inactive')
#     def make_inactive(self, request, queryset):
#         queryset.update(is_active=False)
