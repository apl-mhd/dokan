from rest_framework import serializers
from decimal import Decimal
from sale.models import (
    Sale, SaleItem, SaleStatus, PaymentStatus,
    SaleReturn, SaleReturnItem, SaleReturnStatus, RefundStatus
)
from customer.models import Customer


class SaleItemOutputSerializer(serializers.ModelSerializer):
    """Serializer for sale items in output (read-only)"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)

    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit', 'unit_name',
                  'unit_price', 'line_total', 'created_at']
        read_only_fields = ['line_total',
                            'created_at', 'product_name', 'unit_name']


class SaleItemInputSerializer(serializers.Serializer):
    """Serializer for sale item input (used in create/update operations)"""
    product = serializers.IntegerField(required=True)
    quantity = serializers.DecimalField(
        max_digits=10, decimal_places=4, required=True)
    unit = serializers.IntegerField(required=True)
    unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=True)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Quantity must be greater than zero.")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative.")
        return value


class SaleCreateInputSerializer(serializers.Serializer):
    """Serializer for creating a sale"""
    customer = serializers.IntegerField(required=True)
    warehouse = serializers.IntegerField(required=True)
    items = SaleItemInputSerializer(many=True, required=True)
    status = serializers.ChoiceField(
        choices=SaleStatus.choices,
        default=SaleStatus.PENDING,
        required=False
    )
    sub_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    tax = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    delivery_charge = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    paid_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    invoice_date = serializers.DateField(required=False)

    def validate_items(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one item is required.")
        return value


class SaleUpdateInputSerializer(serializers.Serializer):
    """Serializer for updating a sale"""
    id = serializers.IntegerField(required=True)
    items = SaleItemInputSerializer(many=True, required=True)
    status = serializers.ChoiceField(
        choices=SaleStatus.choices,
        required=False
    )
    sub_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    tax = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    delivery_charge = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    paid_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)

    def validate_items(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one item is required.")
        return value


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name']


class SaleItemSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(source='sale.customer', read_only=True)

    class Meta:
        model = SaleItem
        exclude = ['sale']
        read_only_fields = ['line_total', 'customer']


class SaleSerializer(serializers.ModelSerializer):
    """Serializer for sale output (read operations)"""
    items = SaleItemOutputSerializer(many=True, read_only=True)
    status = serializers.SerializerMethodField()
    # Keep for backward compatibility but not used in frontend
    return_status = serializers.SerializerMethodField()
    customer_name = serializers.CharField(
        source='customer.name', read_only=True)
    customer_phone = serializers.CharField(
        source='customer.phone', read_only=True)
    customer_address = serializers.CharField(
        source='customer.address', read_only=True)
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    company_address = serializers.CharField(
        source='company.address', read_only=True, allow_blank=True)
    company_phone = serializers.CharField(
        source='company.phone', read_only=True, allow_blank=True)
    company_email = serializers.CharField(
        source='company.email', read_only=True, allow_blank=True)

    class Meta:
        model = Sale
        fields = '__all__'
        read_only_fields = ['grand_total', 'company',
                            'created_by', 'created_at', 'updated_at']

    def get_status(self, obj):
        """
        Return combined status that includes return info:
        - If delivered and fully returned -> 'returned'
        - If delivered and partially returned -> 'partial_return'
        - Otherwise return the original status
        """
        original_status = obj.status

        # Only modify status if it's delivered and has returns
        if original_status != SaleStatus.DELIVERED:
            return original_status

        return_status = self.get_return_status(obj)

        if return_status == 'fully_returned':
            return SaleStatus.RETURNED
        elif return_status == 'partially_returned':
            return SaleStatus.PARTIALLY_RETURNED

        return original_status

    def get_return_status(self, obj):
        """
        Return status for a sale based on non-cancelled sale returns:
        - not_returned
        - partially_returned
        - fully_returned
        """
        items = getattr(obj, 'items', None)
        if not items:
            return 'not_returned'

        any_returned = False
        all_fully_returned = True

        for sale_item in items.all() if hasattr(items, 'all') else items:
            # Prefer prefetched attr to avoid DB hits
            return_items = getattr(sale_item, 'active_return_items', None)
            if return_items is None:
                return_items = sale_item.return_items.filter(
                    sale_return__status__in=[
                        SaleReturnStatus.PENDING, SaleReturnStatus.COMPLETED
                    ]
                )

            returned_qty = sum(
                (ri.returned_quantity for ri in return_items),
                Decimal('0.0000')
            )

            if returned_qty > 0:
                any_returned = True

            if returned_qty < sale_item.quantity:
                all_fully_returned = False

        if not any_returned:
            return 'not_returned'
        if all_fully_returned:
            return 'fully_returned'
        return 'partially_returned'

    def validate_paid_amount(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Paid amount cannot be negative.")
        return value

    def validate_discount(self, value):
        if value < 0:
            raise serializers.ValidationError("Discount cannot be negative.")
        return value

    def validate_tax(self, value):
        if value < 0:
            raise serializers.ValidationError("Tax cannot be negative.")
        return value

    def validate_delivery_charge(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Delivery charge cannot be negative.")
        return value


# ================= SALE RETURN SERIALIZERS =================

class SaleReturnItemOutputSerializer(serializers.ModelSerializer):
    """Serializer for sale return items in output (read-only)"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    sale_item_id = serializers.IntegerField(
        source='sale_item.id', read_only=True)

    class Meta:
        model = SaleReturnItem
        fields = [
            'id', 'sale_item_id', 'product', 'product_name',
            'returned_quantity', 'unit', 'unit_name', 'unit_price',
            'line_total', 'condition', 'condition_notes', 'created_at'
        ]
        read_only_fields = ['line_total',
                            'created_at', 'product_name', 'unit_name']


class SaleReturnItemInputSerializer(serializers.Serializer):
    """Serializer for sale return item input (used in create/update operations)"""
    sale_item_id = serializers.IntegerField(required=True)
    returned_quantity = serializers.DecimalField(
        max_digits=10, decimal_places=4, required=True)
    condition = serializers.ChoiceField(
        choices=['good', 'damaged', 'defective', 'expired', 'wrong_item'],
        default='good',
        required=False
    )
    condition_notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)

    def validate_returned_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Returned quantity must be greater than zero.")
        return value


class SaleReturnCreateInputSerializer(serializers.Serializer):
    """Serializer for creating a sale return"""
    sale_id = serializers.IntegerField(required=True)
    return_date = serializers.DateField(required=False)
    return_reason = serializers.CharField(required=True)
    items = SaleReturnItemInputSerializer(many=True, required=True)
    tax = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    refunded_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0.00)
    notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)

    def validate_items(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one item is required.")
        return value

    def validate_tax(self, value):
        if value < 0:
            raise serializers.ValidationError("Tax cannot be negative.")
        return value

    def validate_discount(self, value):
        if value < 0:
            raise serializers.ValidationError("Discount cannot be negative.")
        return value

    def validate_refunded_amount(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Refunded amount cannot be negative.")
        return value


class SaleReturnUpdateInputSerializer(serializers.Serializer):
    """Serializer for updating a sale return"""
    id = serializers.IntegerField(required=True)
    return_date = serializers.DateField(required=False)
    return_reason = serializers.CharField(required=False)
    items = SaleReturnItemInputSerializer(many=True, required=True)
    tax = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    refunded_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False)
    notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)

    def validate_items(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one item is required.")
        return value

    def validate_tax(self, value):
        if value and value < 0:
            raise serializers.ValidationError("Tax cannot be negative.")
        return value

    def validate_discount(self, value):
        if value and value < 0:
            raise serializers.ValidationError("Discount cannot be negative.")
        return value

    def validate_refunded_amount(self, value):
        if value and value < 0:
            raise serializers.ValidationError(
                "Refunded amount cannot be negative.")
        return value


class SaleReturnSerializer(serializers.ModelSerializer):
    """Serializer for sale return output (read operations)"""
    items = SaleReturnItemOutputSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(
        source='customer.name', read_only=True)
    customer_phone = serializers.CharField(
        source='customer.phone', read_only=True)
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True)
    sale_invoice_number = serializers.CharField(
        source='sale.invoice_number', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True)

    class Meta:
        model = SaleReturn
        fields = '__all__'
        read_only_fields = [
            'grand_total', 'sub_total', 'company', 'customer', 'warehouse',
            'created_by', 'updated_by', 'created_at', 'updated_at',
            'completed_at', 'cancelled_at', 'return_number', 'refund_status'
        ]
