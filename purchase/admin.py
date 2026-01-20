from django.contrib import admin
from .models import Purchase, PurchaseItem, PurchaseReturn, PurchaseReturnItem


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0
    readonly_fields = ('line_total', 'created_at')


class PurchaseReturnItemInline(admin.TabularInline):
    model = PurchaseReturnItem
    extra = 0
    readonly_fields = ('line_total', 'created_at')


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'supplier', 'grand_total', 
                    'status', 'payment_status', 'invoice_date', 'company')
    list_filter = ('status', 'payment_status', 'company', 'invoice_date')
    search_fields = ('invoice_number', 'supplier__name')
    readonly_fields = ('created_at', 'updated_at', 'completed_at', 'cancelled_at')
    inlines = [PurchaseItemInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('company', 'supplier', 'warehouse', 'invoice_number', 'invoice_date')
        }),
        ('Financial Details', {
            'fields': ('sub_total', 'tax', 'discount', 'delivery_charge', 
                      'grand_total', 'paid_amount', 'payment_status')
        }),
        ('Status', {
            'fields': ('status', 'completed_at', 'cancelled_at')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Audit', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = ('purchase', 'product', 'quantity', 'unit', 'unit_price', 'line_total')
    list_filter = ('company', 'purchase__invoice_date')
    search_fields = ('product__name', 'purchase__invoice_number')


@admin.register(PurchaseReturn)
class PurchaseReturnAdmin(admin.ModelAdmin):
    list_display = ('return_number', 'purchase', 'supplier', 'grand_total', 
                    'status', 'return_date', 'company')
    list_filter = ('status', 'company', 'return_date')
    search_fields = ('return_number', 'purchase__invoice_number', 'supplier__name')
    readonly_fields = ('return_number', 'sub_total', 'tax', 'discount', 'grand_total',
                      'completed_at', 'cancelled_at', 'created_at', 'updated_at')
    inlines = [PurchaseReturnItemInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('company', 'purchase', 'supplier', 'warehouse', 
                      'return_number', 'return_date')
        }),
        ('Financial Details', {
            'fields': ('sub_total', 'tax', 'discount', 'grand_total', 'refund_amount')
        }),
        ('Status', {
            'fields': ('status', 'completed_at', 'cancelled_at')
        }),
        ('Reason & Notes', {
            'fields': ('reason', 'notes')
        }),
        ('Audit', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PurchaseReturnItem)
class PurchaseReturnItemAdmin(admin.ModelAdmin):
    list_display = ('purchase_return', 'product', 'quantity', 
                    'unit', 'unit_price', 'line_total')
    list_filter = ('company', 'purchase_return__return_date')
    search_fields = ('product__name', 'purchase_return__return_number')
