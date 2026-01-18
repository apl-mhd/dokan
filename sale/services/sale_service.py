from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from inventory.models import Stock, StockTransaction, TransactionType, StockDirection
from product.models import Product, Unit
from sale.models import Sale, SaleItem, SaleStatus, PaymentStatus
from customer.models import Customer
from warehouse.models import Warehouse
from sale.serializers import (
    SaleCreateInputSerializer,
    SaleUpdateInputSerializer
)
from rest_framework.exceptions import ValidationError
from core.services.invoice_number import InvoiceNumberGenerator
from core.models import DocumentType
from accounting.services.ledger_service import LedgerService


class SaleService:

    @staticmethod
    def _validate_company_access(company, **kwargs):
        """
        Validate that all related objects belong to the same company.
        Prevents cross-company data access.
        """
        if 'customer' in kwargs:
            customer = kwargs['customer']
            if customer.company != company:
                raise ValidationError(
                    "Customer does not belong to your company.")

        if 'warehouse' in kwargs:
            warehouse = kwargs['warehouse']
            if warehouse.company != company:
                raise ValidationError(
                    "Warehouse does not belong to your company.")

        if 'sale' in kwargs:
            sale = kwargs['sale']
            if sale.company != company:
                raise ValidationError("Sale does not belong to your company.")

    @staticmethod
    def _update_stock(product, warehouse, company, quantity, unit, operation='subtract'):
        """
        Update stock quantity for a product in a warehouse for a specific company.
        IMPORTANT: Converts quantity to base unit before storing.

        Args:
            product: Product instance
            warehouse: Warehouse instance
            company: Company instance
            quantity: Decimal quantity in the given unit
            unit: Unit instance for the quantity
            operation: 'add' or 'subtract'

        Returns:
            tuple: (Stock instance, base_unit_quantity)

        Raises:
            ValidationError: If stock is insufficient for subtract operation
        """
        # Convert quantity to base unit
        base_unit_quantity = unit.convert_to_base_unit(quantity)

        stock, _ = Stock.objects.get_or_create(
            product=product,
            warehouse=warehouse,
            company=company,
            defaults={'quantity': Decimal('0.00')}
        )

        if operation == 'subtract':
            if stock.quantity < base_unit_quantity:
                # Get base unit name for better error message
                base_unit_name = product.base_unit.name if product.base_unit else "base units"
                raise ValidationError(
                    f"Insufficient stock for {product.name}. "
                    f"Available: {stock.quantity} {base_unit_name}, "
                    f"Requested: {quantity} {unit.name} ({base_unit_quantity} {base_unit_name})"
                )
            stock.quantity -= base_unit_quantity
        elif operation == 'add':
            stock.quantity += base_unit_quantity

        stock.save(update_fields=["quantity"])
        return stock, base_unit_quantity

    @staticmethod
    def _create_stock_transaction(product, stock, unit, company, original_quantity, base_unit_quantity, direction, transaction_type, reference_id, note=None):
        """
        Create a stock transaction record.
        Records ORIGINAL quantity in transaction for audit trail.

        Args:
            product: Product instance
            stock: Stock instance
            unit: Unit instance (the unit used in the transaction)
            company: Company instance
            original_quantity: Decimal quantity in original unit (for audit)
            base_unit_quantity: Decimal quantity in base unit (used for stock)
            direction: StockDirection.IN or StockDirection.OUT
            transaction_type: TransactionType enum value
            reference_id: ID of the related purchase/sale
            note: Optional note string

        Returns:
            StockTransaction instance
        """
        stock_transaction = StockTransaction.objects.create(
            product=product,
            quantity=base_unit_quantity,  # Store in base unit for consistency
            stock=stock,
            unit=unit,  # Keep original unit for reference
            company=company,
            direction=direction,
            transaction_type=transaction_type,
            reference_id=reference_id,
            balance_after=stock.quantity,
            note=note or f"Original: {original_quantity} {unit.name} = {base_unit_quantity} base units",
        )
        return stock_transaction

    @staticmethod
    def _revert_old_items_stock(sale, old_items, warehouse, company):
        """
        Revert stock for old sale items (add quantities back).
        Used when updating a sale.
        IMPORTANT: Converts to base unit before adding.

        Args:
            sale: Sale instance
            old_items: QuerySet of old SaleItem instances
            warehouse: Warehouse instance
            company: Company instance
        """
        for old_item in old_items:
            if old_item.quantity > 0:
                stock, base_qty = SaleService._update_stock(
                    old_item.product, warehouse, company, old_item.quantity, old_item.unit, operation='add'
                )
                SaleService._create_stock_transaction(
                    product=old_item.product,
                    stock=stock,
                    unit=old_item.unit,
                    company=company,
                    original_quantity=old_item.quantity,
                    base_unit_quantity=base_qty,
                    direction=StockDirection.IN,
                    transaction_type=TransactionType.SALE_RETURN,
                    reference_id=sale.id,
                    note=f"Sale update - reverted {old_item.quantity} {old_item.unit.name} ({base_qty} base units) from {sale.invoice_number}",
                )

    @staticmethod
    def _process_sale_items(sale, items, warehouse, company, is_update=False):
        """
        Process sale items and update stock accordingly.
        IMPORTANT: Converts all quantities to base unit before deducting from stock.

        Example: If user sells 50kg * 2 (quantity=50, unit=kg, with conversion_factor=1.0)
                 Stock will be reduced by 100kg in base unit.

        Args:
            sale: Sale instance
            items: List of item dictionaries
            warehouse: Warehouse instance
            company: Company instance
            is_update: Boolean indicating if this is an update operation

        Returns:
            tuple: (sale_items list, sub_total Decimal)
        """
        sub_total = Decimal('0.00')
        sale_items = []

        for item in items:
            product = get_object_or_404(Product, id=item['product'])
            unit = get_object_or_404(Unit, id=item['unit'])
            quantity = Decimal(str(item['quantity']))
            unit_price = Decimal(str(item['unit_price']))
            line_total = quantity * unit_price
            sub_total += line_total

            sale_items.append(SaleItem(
                sale=sale,
                company=company,  # Automatically set company
                product=product,
                quantity=quantity,
                unit=unit,
                unit_price=unit_price,
                line_total=line_total,
            ))

            # Update stock for new items (deduct from stock) - CONVERTED TO BASE UNIT
            if quantity > 0:
                stock, base_unit_quantity = SaleService._update_stock(
                    product, warehouse, company, quantity, unit, operation='subtract'
                )
                transaction_note = (
                    f"Sale update - deducted {quantity} {unit.name} ({base_unit_quantity} base units) from {sale.invoice_number}"
                    if is_update
                    else f"Sale {sale.invoice_number} - {quantity} {unit.name} = {base_unit_quantity} base units"
                )
                SaleService._create_stock_transaction(
                    product=product,
                    stock=stock,
                    unit=unit,
                    company=company,
                    original_quantity=quantity,
                    base_unit_quantity=base_unit_quantity,
                    direction=StockDirection.OUT,
                    transaction_type=TransactionType.SALE,
                    reference_id=sale.id,
                    note=transaction_note,
                )

        return sale_items, sub_total
    
    @staticmethod
    def _calculate_payment_status(paid_amount, grand_total):
        """Calculate payment status based on paid_amount and grand_total"""
        if paid_amount <= 0:
            return PaymentStatus.UNPAID
        elif paid_amount >= grand_total:
            if paid_amount > grand_total:
                return PaymentStatus.OVERPAID
            else:
                return PaymentStatus.PAID
        else:
            return PaymentStatus.PARTIAL

    @staticmethod
    def update_sale(data, user, company):
        """
        Update an existing sale.
        Company-aware: ensures user can only update sales from their company.

        Args:
            data: Dictionary containing sale data
            user: User instance
            company: Company instance from request

        Returns:
            Sale instance
        """
        # Validate input data using serializer
        serializer = SaleUpdateInputSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        sale = get_object_or_404(Sale.objects.filter(
            company=company), id=validated_data.get("id"))
        items = validated_data.get("items")

        # Validate company access
        SaleService._validate_company_access(company, sale=sale)

        try:
            with transaction.atomic():
                # Get old items before deleting for stock adjustment
                old_items = list(sale.items.all())
                warehouse = sale.warehouse

                # Validate warehouse belongs to company
                SaleService._validate_company_access(
                    company, warehouse=warehouse)

                # Delete old ledger entries before updating
                LedgerService.delete_ledger_entries_for_object(sale, company)

                # Revert stock for old items first (add back to stock)
                SaleService._revert_old_items_stock(
                    sale, old_items, warehouse, company)

                # Delete existing items
                sale.items.all().delete()

                # Update sale fields if provided
                if 'status' in validated_data:
                    sale.status = validated_data['status']
                if 'notes' in validated_data:
                    sale.notes = validated_data['notes']
                sale.updated_by = user
                sale.save()

                # Process new items and update stock
                sale_items, sub_total = SaleService._process_sale_items(
                    sale=sale,
                    items=items,
                    warehouse=warehouse,
                    company=company,
                    is_update=True
                )

                SaleItem.objects.bulk_create(sale_items)
                
                # Calculate totals
                sale.sub_total = sub_total
                sale.tax = Decimal(str(validated_data.get('tax', 0.00)))
                sale.discount = Decimal(str(validated_data.get('discount', 0.00)))
                sale.delivery_charge = Decimal(str(validated_data.get('delivery_charge', 0.00)))
                sale.grand_total = sub_total + sale.tax + sale.delivery_charge - sale.discount
                
                # Handle payment fields
                paid_amount = Decimal(str(validated_data.get('paid_amount', 0.00)))
                sale.paid_amount = paid_amount
                if 'payment_status' in validated_data:
                    sale.payment_status = validated_data['payment_status']
                else:
                    # Auto-calculate payment status if not provided
                    sale.payment_status = SaleService._calculate_payment_status(paid_amount, sale.grand_total)
                
                sale.save(update_fields=["sub_total", "tax", "discount", "delivery_charge", "grand_total", "paid_amount", "payment_status"])

                # Create accounting ledger entries (double-entry)
                if sale.grand_total > 0:
                    LedgerService.create_sale_ledger_entry(sale, company)
                    # Update customer balance
                    LedgerService.update_party_balance(sale.customer, company)

                return sale

        except IntegrityError as e:
            raise ValidationError(str(e))

    @staticmethod
    def create_sale(data, user, company):
        """
        Create a new sale.
        Company-aware: automatically sets company and validates all related objects.

        Args:
            data: Dictionary containing sale data
            user: User instance
            company: Company instance from request

        Returns:
            Sale instance
        """
        # Validate input data using serializer
        serializer = SaleCreateInputSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        warehouse = get_object_or_404(Warehouse.objects.filter(
            company=company), id=validated_data.get("warehouse"))
        customer = get_object_or_404(Customer.objects.filter(
            company=company), id=validated_data.get("customer"))
        items = validated_data.get("items")

        # Validate company access for all related objects
        SaleService._validate_company_access(
            company, customer=customer, warehouse=warehouse)

        try:
            with transaction.atomic():
                # Generate invoice number using InvoiceNumberGenerator
                invoice_number = InvoiceNumberGenerator.generate_invoice_number(
                    company=company,
                    doc_type=DocumentType.SALES_ORDER
                )

                sale = Sale.objects.create(
                    invoice_number=invoice_number,
                    status=validated_data.get("status", SaleStatus.PENDING),
                    created_by=user,
                    warehouse=warehouse,
                    customer=customer,
                    company=company,  # Automatically set company
                    notes=validated_data.get("notes", ""),
                    invoice_date=validated_data.get("invoice_date"),
                )

                # Process items and update stock
                sale_items, sub_total = SaleService._process_sale_items(
                    sale=sale,
                    items=items,
                    warehouse=warehouse,
                    company=company,
                    is_update=False
                )

                SaleItem.objects.bulk_create(sale_items)
                
                # Calculate totals
                sale.sub_total = sub_total
                sale.tax = Decimal(str(validated_data.get('tax', 0.00)))
                sale.discount = Decimal(str(validated_data.get('discount', 0.00)))
                sale.delivery_charge = Decimal(str(validated_data.get('delivery_charge', 0.00)))
                sale.grand_total = sub_total + sale.tax + sale.delivery_charge - sale.discount
                
                # Handle payment fields
                paid_amount = Decimal(str(validated_data.get('paid_amount', 0.00)))
                sale.paid_amount = paid_amount
                if 'payment_status' in validated_data:
                    sale.payment_status = validated_data['payment_status']
                else:
                    # Auto-calculate payment status if not provided
                    sale.payment_status = SaleService._calculate_payment_status(paid_amount, sale.grand_total)
                
                sale.save(update_fields=["sub_total", "tax", "discount", "delivery_charge", "grand_total", "paid_amount", "payment_status"])

                # Create accounting ledger entries (double-entry)
                if sale.grand_total > 0:
                    LedgerService.create_sale_ledger_entry(sale, company)
                    # Update customer balance
                    LedgerService.update_party_balance(sale.customer, company)

                return sale

        except IntegrityError as e:
            raise ValidationError(str(e))
