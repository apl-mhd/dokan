from django.contrib import admin
from .models import Sale, SaleItem
from customer.models import Customer
from product.models import Product, Unit


# admin.site.register([
#     Sale,
#     SaleItem,
# ])

# -------------------------
# Inline for SaleItem
# -------------------------


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    fields = ('product', 'quantity', 'unit',
              'unit_price', 'line_total', 'company')
    readonly_fields = ('line_total', 'company')

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        # Auto-populate company from parent Sale
        if obj:
            formset.form.base_fields['company'].initial = obj.company
        return formset

    # Automatically calculate line_total
    def save_model(self, request, obj, form, change):
        obj.line_total = obj.quantity * obj.unit_price
        super().save_model(request, obj, form, change)

# -------------------------
# Admin for Sale
# -------------------------


class SaleAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer_name', 'warehouse_name',
                    'company_name', 'invoice_date', 'grand_total', 'status', 'created_at')
    list_filter = ('status', 'invoice_date', 'customer',
                   'warehouse', 'company', 'created_at')
    search_fields = ('invoice_number', 'customer__name',
                     'warehouse__name', 'company__name')
    readonly_fields = ('grand_total', 'created_at',
                       'updated_at', 'created_by', 'updated_by')
    inlines = [SaleItemInline]

    fieldsets = (
        ('Sale Information', {
            'fields': ('invoice_number', 'invoice_date', 'status')
        }),
        ('Related Entities', {
            'fields': ('customer', 'warehouse', 'company')
        }),
        ('Financial', {
            'fields': ('grand_total',)
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # Display customer name
    @admin.display(description='Customer')
    def customer_name(self, obj):
        return obj.customer.name if obj.customer else '-'

    # Display warehouse name
    @admin.display(description='Warehouse')
    def warehouse_name(self, obj):
        return obj.warehouse.name if obj.warehouse else '-'

    # Display company name
    @admin.display(description='Company')
    def company_name(self, obj):
        return obj.company.name if obj.company else '-'

    # Automatically calculate grand_total
    def save_model(self, request, obj, form, change):
        # Set created_by on creation
        if not change and not obj.created_by:
            obj.created_by = request.user
        # Always set updated_by
        obj.updated_by = request.user

        super().save_model(request, obj, form, change)

        # Calculate grand_total from items
        total = sum(item.line_total for item in obj.items.all())
        if obj.grand_total != total:
            obj.grand_total = total
            obj.save()


# -------------------------
# Unregister if already registered
# -------------------------
try:
    admin.site.unregister(Sale)
except admin.sites.NotRegistered:
    pass

# -------------------------
# Register admin models
# -------------------------
admin.site.register(Sale, SaleAdmin)
