from django.contrib import admin
from .models import Customer, Sale, SaleItem, Product, Unit

# -------------------------
# Inline for SaleItem
# -------------------------
class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    fields = ('product', 'quantity', 'unit', 'unit_price', 'sub_total')
    readonly_fields = ('sub_total',)

    # Automatically calculate sub_total
    def save_model(self, request, obj, form, change):
        obj.sub_total = obj.quantity * obj.unit_price
        super().save_model(request, obj, form, change)

# -------------------------
# Admin for Sale
# -------------------------
class SaleAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer_name', 'invoice_date', 'grand_total', 'status')
    list_filter = ('status', 'invoice_date', 'customer')
    search_fields = ('invoice_number', 'customer__name')
    inlines = [SaleItemInline]

    # Display customer name
    @admin.display(description='Customer')
    def customer_name(self, obj):
        return obj.customer.name

    # Automatically calculate grand_total
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        total = sum(item.sub_total for item in obj.items.all())
        if obj.grand_total != total:
            obj.grand_total = total
            obj.save()

# -------------------------
# Admin for Customer
# -------------------------
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'is_active', 'created_at')
    search_fields = ('name', 'email', 'phone')
    list_filter = ('is_active', 'created_at')

# -------------------------
# Unregister if already registered
# -------------------------
for model in [Customer, Sale]:
    try:
        admin.site.unregister(model)
    except admin.sites.NotRegistered:
        pass

# -------------------------
# Register admin models
# -------------------------
admin.site.register(Customer, CustomerAdmin)
admin.site.register(Sale, SaleAdmin)
