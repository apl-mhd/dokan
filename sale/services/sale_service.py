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
from payment.models import Payment, PaymentType, PaymentMethod, PaymentStatus as PayStatus
from payment.services.payment_fifo_service import PaymentFIFOService


class SaleService:
    AUTO_PAYMENT_REFERENCE_PREFIX = "AUTO-SALE-PAYMENT-"
    AUTO_PAYMENT_NOTE = "AUTO: Created/updated from Sale paid_amount"

    @staticmethod
    def _sync_auto_payment_from_paid_amount(sale, user, company):
        """
        Ensure the Payment table has a single auto-payment row reflecting sale.paid_amount.
        This does NOT create ledger entries (sale ledger already handles paid_amount when delivered).
        """
        ref = f"{SaleService.AUTO_PAYMENT_REFERENCE_PREFIX}{sale.id}"

        qs = Payment.objects.filter(company=company, sale=sale, reference_number=ref)
        existing = qs.order_by("-id").first()

        # If paid_amount is zero/negative, remove any auto payment
        if (sale.paid_amount or Decimal("0.00")) <= 0:
            qs.delete()
            return

        if existing is None:
            Payment.objects.create(
                company=company,
                payment_type=PaymentType.RECEIVED,
                customer=sale.customer,
                supplier=None,
                sale=sale,
                purchase=None,
                payment_method=PaymentMethod.CASH,
                amount=sale.paid_amount,
                date=sale.invoice_date,
                reference_number=ref,
                status=PayStatus.COMPLETED,
                notes=SaleService.AUTO_PAYMENT_NOTE,
                created_by=user,
            )
            return

        # Keep a single row; remove duplicates if any
        qs.exclude(pk=existing.pk).delete()

        existing.customer = sale.customer
        existing.supplier = None
        existing.purchase = None
        existing.payment_type = PaymentType.RECEIVED
        existing.payment_method = PaymentMethod.CASH
        existing.amount = sale.paid_amount
        existing.date = sale.invoice_date
        existing.status = PayStatus.COMPLETED
        existing.notes = SaleService.AUTO_PAYMENT_NOTE
        existing.updated_by = user
        existing.save()

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
    def _create_stock_transaction(product, stock, unit, company, original_quantity, base_unit_quantity, direction, transaction_type, reference_id, note=None, source_object=None):
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
        from django.contrib.contenttypes.models import ContentType

        content_type = None
        object_id = None
        if source_object is not None:
            content_type = ContentType.objects.get_for_model(source_object.__class__)
            object_id = source_object.id

        stock_transaction = StockTransaction.objects.create(
            product=product,
            quantity=base_unit_quantity,  # Store in base unit for consistency
            stock=stock,
            unit=unit,  # Keep original unit for reference
            company=company,
            direction=direction,
            transaction_type=transaction_type,
            reference_id=reference_id,
            content_type=content_type,
            object_id=object_id,
            balance_after=stock.quantity,
            note=note or f"Original: {original_quantity} {unit.name} = {base_unit_quantity} base units",
        )
        return stock_transaction

    @staticmethod
    def _revert_old_items_stock(sale, old_items, warehouse, company, should_revert_stock=True):
        """
        Revert stock for old sale items (add quantities back).
        Used when updating a sale or cancelling a delivered sale.
        IMPORTANT: Converts to base unit before adding.

        Args:
            sale: Sale instance
            old_items: QuerySet of old SaleItem instances
            warehouse: Warehouse instance
            company: Company instance
            should_revert_stock: Boolean indicating if stock should be reverted (only if old status was delivered)
        """
        for old_item in old_items:
            if old_item.quantity > 0 and should_revert_stock:
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
                    source_object=sale,
                    note=f"Sale update - reverted {old_item.quantity} {old_item.unit.name} ({base_qty} base units) from {sale.invoice_number}",
                )

    @staticmethod
    def _apply_ledger_entries(sale, company):
        """
        Apply ledger entries for a delivered sale.
        This method should only be called when sale status is 'delivered'.
        Note: Inventory is handled separately in _process_sale_items.

        Args:
            sale: Sale instance
            company: Company instance
        """
        # Create ledger entries
        if sale.grand_total > 0:
            # Create sale ledger entry (Debit: Customer Receivable)
            LedgerService.create_sale_ledger_entry(sale, company)

            # Create payment ledger entry if paid_amount > 0 (Credit: Customer Receivable)
            if sale.paid_amount > 0:
                from types import SimpleNamespace
                payment_obj = SimpleNamespace(
                    reference_number=sale.invoice_number or f"SAL-{sale.id}",
                    amount=sale.paid_amount,
                    date=sale.invoice_date,
                    notes=sale.notes or ""
                )
                LedgerService.create_payment_ledger_entry(
                    payment_obj, company, sale.customer, payment_type='received', source_object=sale)

            # Update customer balance
            LedgerService.update_party_balance(sale.customer, company)

    @staticmethod
    def _process_sale_items(sale, items, warehouse, company, is_update=False, should_update_stock=True):
        """
        Process sale items and optionally update stock accordingly.
        IMPORTANT: Converts all quantities to base unit before deducting from stock.

        Example: If user sells 50kg * 2 (quantity=50, unit=kg, with conversion_factor=1.0)
                 Stock will be reduced by 100kg in base unit.

        Args:
            sale: Sale instance
            items: List of item dictionaries
            warehouse: Warehouse instance
            company: Company instance
            is_update: Boolean indicating if this is an update operation
            should_update_stock: Boolean indicating if stock should be updated (only for delivered status)

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
            # Only update stock if should_update_stock is True (i.e., status is delivered)
            if quantity > 0 and should_update_stock:
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
                    source_object=sale,
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
                # Store old status to detect transitions
                old_status = sale.status
                old_items = list(sale.items.all())
                warehouse = sale.warehouse

                # Validate warehouse belongs to company
                SaleService._validate_company_access(
                    company, warehouse=warehouse)

                # Get new status
                new_status = validated_data.get('status', old_status)

                # Handle status transitions:
                # - If old status was delivered, we need to reverse inventory/ledger
                # - If new status is delivered, we need to apply inventory/ledger
                # - If old status was delivered and new status is cancelled, reverse everything
                # - If old status was delivered and new status is pending, reverse everything
                should_revert_old = (old_status == SaleStatus.DELIVERED)
                should_apply_new = (new_status == SaleStatus.DELIVERED)

                # Delete old ledger entries if old status was delivered
                if should_revert_old:
                    LedgerService.delete_ledger_entries_for_object(
                        sale, company)

                # Revert stock for old items only if old status was delivered
                if should_revert_old:
                    SaleService._revert_old_items_stock(
                        sale, old_items, warehouse, company, should_revert_stock=True)

                # Delete existing items
                sale.items.all().delete()

                # Update sale fields if provided
                if 'status' in validated_data:
                    sale.status = new_status
                if 'notes' in validated_data:
                    sale.notes = validated_data['notes']
                sale.updated_by = user
                sale.save()

                # Process new items - only update stock if new status is delivered
                sale_items, sub_total = SaleService._process_sale_items(
                    sale=sale,
                    items=items,
                    warehouse=warehouse,
                    company=company,
                    is_update=True,
                    should_update_stock=should_apply_new
                )

                SaleItem.objects.bulk_create(sale_items)

                # Calculate totals
                sale.sub_total = sub_total
                sale.tax = Decimal(str(validated_data.get('tax', 0.00)))
                sale.discount = Decimal(
                    str(validated_data.get('discount', 0.00)))
                sale.delivery_charge = Decimal(
                    str(validated_data.get('delivery_charge', 0.00)))
                sale.grand_total = sub_total + sale.tax + sale.delivery_charge - sale.discount

                # Handle payment fields
                paid_amount = Decimal(
                    str(validated_data.get('paid_amount', 0.00)))
                sale.paid_amount = paid_amount
                # Save first to ensure sale exists for FIFO calculation
                sale.save(update_fields=["sub_total", "tax", "discount",
                          "delivery_charge", "grand_total", "paid_amount"])
                # Always auto-calculate payment status using FIFO formula
                PaymentFIFOService._update_invoice_payment_status(sale, 'sale')

                # Apply ledger entries only if new status is delivered
                if should_apply_new:
                    SaleService._apply_ledger_entries(sale, company)
                elif new_status in [SaleStatus.PENDING, SaleStatus.CANCELLED]:
                    # If status is pending or cancelled, ensure no ledger entries exist
                    # and update customer balance
                    LedgerService.delete_ledger_entries_for_object(
                        sale, company)
                    LedgerService.update_party_balance(sale.customer, company)

                # Sync Payment table row from paid_amount (all statuses)
                SaleService._sync_auto_payment_from_paid_amount(sale, user, company)

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

                sale_status = validated_data.get("status", SaleStatus.PENDING)
                sale = Sale.objects.create(
                    invoice_number=invoice_number,
                    status=sale_status,
                    created_by=user,
                    warehouse=warehouse,
                    customer=customer,
                    company=company,  # Automatically set company
                    notes=validated_data.get("notes", ""),
                    invoice_date=validated_data.get("invoice_date"),
                )

                # Process items - only update stock if status is delivered
                should_update_stock = (sale_status == SaleStatus.DELIVERED)
                sale_items, sub_total = SaleService._process_sale_items(
                    sale=sale,
                    items=items,
                    warehouse=warehouse,
                    company=company,
                    is_update=False,
                    should_update_stock=should_update_stock
                )

                SaleItem.objects.bulk_create(sale_items)

                # Calculate totals
                sale.sub_total = sub_total
                sale.tax = Decimal(str(validated_data.get('tax', 0.00)))
                sale.discount = Decimal(
                    str(validated_data.get('discount', 0.00)))
                sale.delivery_charge = Decimal(
                    str(validated_data.get('delivery_charge', 0.00)))
                sale.grand_total = sub_total + sale.tax + sale.delivery_charge - sale.discount

                # Handle payment fields
                paid_amount = Decimal(
                    str(validated_data.get('paid_amount', 0.00)))
                sale.paid_amount = paid_amount
                # Save first to ensure sale exists for FIFO calculation
                sale.save(update_fields=["sub_total", "tax", "discount",
                          "delivery_charge", "grand_total", "paid_amount"])
                # Always auto-calculate payment status using FIFO formula
                PaymentFIFOService._update_invoice_payment_status(sale, 'sale')

                # Create accounting ledger entries only if status is delivered
                if sale_status == SaleStatus.DELIVERED:
                    SaleService._apply_ledger_entries(sale, company)

                # Sync Payment table row from paid_amount (all statuses)
                SaleService._sync_auto_payment_from_paid_amount(sale, user, company)

                return sale

        except IntegrityError as e:
            raise ValidationError(str(e))
