from django.contrib import admin
from payment.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'payment_type', 'party_name_display', 'payment_method',
                    'amount', 'date', 'status', 'invoice_display', 'created_at')
    list_filter = ('payment_type', 'payment_method',
                   'status', 'date', 'company', 'created_at')
    search_fields = ('customer__name', 'supplier__name', 'reference_number',
                     'sale__invoice_number', 'purchase__invoice_number', 'account_number')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')

    fieldsets = (
        ('Payment Type', {
            'fields': ('company', 'payment_type')
        }),
        ('Party Information', {
            'fields': ('customer', 'supplier', 'sale', 'purchase')
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'amount', 'date', 'status')
        }),
        ('Payment Details', {
            'fields': ('reference_number', 'account_number', 'account_holder_name',
                       'bank_name', 'branch_name')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def party_name_display(self, obj):
        return obj.get_party_name()
    party_name_display.short_description = 'Party'

    def invoice_display(self, obj):
        if obj.payment_type == 'received' and obj.sale:
            return obj.sale.invoice_number
        elif obj.payment_type == 'made' and obj.purchase:
            return obj.purchase.invoice_number
        return '-'
    invoice_display.short_description = 'Invoice'

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
