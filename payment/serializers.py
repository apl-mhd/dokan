from rest_framework import serializers
from payment.models import Payment, PaymentMethod, PaymentStatus, PaymentType


class PaymentInputSerializer(serializers.Serializer):
    """Serializer for creating payments (both customer and supplier)"""
    payment_type = serializers.ChoiceField(
        choices=PaymentType.choices,
        required=True
    )
    customer = serializers.IntegerField(required=False, allow_null=True)
    supplier = serializers.IntegerField(required=False, allow_null=True)
    sale = serializers.IntegerField(required=False, allow_null=True)
    purchase = serializers.IntegerField(required=False, allow_null=True)
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH
    )
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True
    )
    date = serializers.DateField(required=False)
    reference_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    account_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    account_holder_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    bank_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    branch_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    status = serializers.ChoiceField(
        choices=PaymentStatus.choices,
        default=PaymentStatus.COMPLETED
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    def validate_amount(self, value):
        if value == 0:
            raise serializers.ValidationError("Amount cannot be zero")
        return value

    def validate(self, data):
        """Validate party based on payment type"""
        payment_type = data.get('payment_type')

        if payment_type == PaymentType.RECEIVED:
            if not data.get('customer'):
                raise serializers.ValidationError({
                    'customer': 'Customer is required for received payments'
                })
            if data.get('supplier'):
                raise serializers.ValidationError({
                    'supplier': 'Supplier should not be set for received payments'
                })
        elif payment_type == PaymentType.MADE:
            if not data.get('supplier'):
                raise serializers.ValidationError({
                    'supplier': 'Supplier is required for made payments'
                })
            if data.get('customer'):
                raise serializers.ValidationError({
                    'customer': 'Customer should not be set for made payments'
                })
        elif payment_type == PaymentType.CUSTOMER_REFUND:
            if not data.get('customer'):
                raise serializers.ValidationError({
                    'customer': 'Customer is required for customer refund'
                })
            if data.get('supplier'):
                raise serializers.ValidationError({
                    'supplier': 'Supplier should not be set for customer refund'
                })
            if data.get('amount', 0) <= 0:
                raise serializers.ValidationError({
                    'amount': 'Refund amount must be positive'
                })
        elif payment_type == PaymentType.SUPPLIER_REFUND:
            if not data.get('supplier'):
                raise serializers.ValidationError({
                    'supplier': 'Supplier is required for supplier refund'
                })
            if data.get('customer'):
                raise serializers.ValidationError({
                    'customer': 'Customer should not be set for supplier refund'
                })
            if data.get('amount', 0) <= 0:
                raise serializers.ValidationError({
                    'amount': 'Refund amount must be positive'
                })
        elif payment_type == PaymentType.WITHDRAW:
            if not data.get('customer'):
                raise serializers.ValidationError({
                    'customer': 'Customer (owner) is required for owner withdraw'
                })
            if data.get('supplier'):
                raise serializers.ValidationError({
                    'supplier': 'Supplier should not be set for owner withdraw'
                })
            if data.get('amount', 0) <= 0:
                raise serializers.ValidationError({
                    'amount': 'Withdraw amount must be positive'
                })

        return data


class PaymentUpdateSerializer(serializers.Serializer):
    """Serializer for updating payment"""
    id = serializers.IntegerField(required=True)
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        required=False
    )
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False
    )
    date = serializers.DateField(required=False)
    reference_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    account_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    account_holder_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    bank_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    branch_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    status = serializers.ChoiceField(
        choices=PaymentStatus.choices,
        required=False
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    def validate_amount(self, value):
        if value is not None and value == 0:
            raise serializers.ValidationError("Amount cannot be zero")
        return value


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for payment output"""
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    supplier_phone = serializers.CharField(source='supplier.phone', read_only=True)
    sale_invoice_number = serializers.CharField(source='sale.invoice_number', read_only=True)
    purchase_invoice_number = serializers.CharField(source='purchase.invoice_number', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    party_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = [
            'company', 'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]
    
    def get_party_name(self, obj):
        """Get party name based on payment type"""
        return obj.get_party_name()
