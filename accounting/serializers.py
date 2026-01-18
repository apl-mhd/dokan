from rest_framework import serializers
from .models import Ledger, TransactionType


class LedgerSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)
    party_id = serializers.IntegerField(source='party.id', read_only=True)
    party_opening_balance = serializers.DecimalField(
        source='party.opening_balance', max_digits=12, decimal_places=2, read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Ledger
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_amount(self, obj):
        """Calculate net amount (debit - credit)"""
        return float(obj.debit - obj.credit)

    def to_representation(self, instance):
        """Custom representation to include content object info"""
        representation = super().to_representation(instance)

        # Get related object if it exists
        if instance.content_object:
            content_obj = instance.content_object
            if hasattr(content_obj, 'invoice_number'):
                representation['related_invoice_number'] = content_obj.invoice_number
            if hasattr(content_obj, 'id'):
                representation['related_id'] = content_obj.id
            representation['related_type'] = instance.content_type.model if instance.content_type else None

        return representation
