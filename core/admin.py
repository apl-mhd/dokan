from django.contrib import admin
from core.models import DocumentSequence, Party

# @admin.register(Party)
# class PartyAdmin(admin.ModelAdmin):
#     list_display = ('name', 'party_type', 'balance')
#     list_filter = ('party_type',)
#     search_fields = ('name',)
#     readonly_fields = ('created_at', 'updated_at')
#     ordering = ('name',)

admin.site.register([
    Party,
])

@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ('company', 'document_type', 'current_year', 'next_number')
    list_filter = ('company', 'document_type', 'current_year')
    search_fields = ('company__name', 'document_type')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('company', 'document_type', 'current_year')