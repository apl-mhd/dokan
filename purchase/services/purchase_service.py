from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from inventory.models import Stock, StockTransaction, TransactionType, StockDirection
from product.models import Product, Unit
from purchase.models import Purchase, PurchaseItem, PurchaseStatus, PaymentStatus
from supplier.models import Supplier
from warehouse.models import Warehouse
from purchase.serializers import (
    PurchaseCreateInputSerializer,
    PurchaseUpdateInputSerializer
)
from rest_framework.exceptions import ValidationError
from core.services.invoice_number import InvoiceNumberGenerator
from core.models import DocumentType
from accounting.services.ledger_service import LedgerService
from payment.models import Payment, PaymentType, PaymentMethod, PaymentStatus as PayStatus
from payment.services.payment_fifo_service import PaymentFIFOService


class PurchaseService:
    AUTO_PAYMENT_REFERENCE_PREFIX = "AUTO-PURCHASE-PAYMENT-"
    AUTO_PAYMENT_NOTE = "AUTO: Created/updated from Purchase paid_amount"

    @staticmethod
    def _sync_auto_payment_from_paid_amount(purchase, user, company):
        """
        Ensure the Payment table has a single auto-payment row reflecting purchase.paid_amount.
        This does NOT create ledger entries (purchase ledger already handles paid_amount when completed).
        """
        ref = f"{PurchaseService.AUTO_PAYMENT_REFERENCE_PREFIX}{purchase.id}"

        qs = Payment.objects.filter(company=company, purchase=purchase, reference_number=ref)
        existing = qs.order_by("-id").first()

        if (purchase.paid_amount or Decimal("0.00")) <= 0:
            qs.delete()
            return

        if existing is None:
            Payment.objects.create(
                company=company,
                payment_type=PaymentType.MADE,
                customer=None,
                supplier=purchase.supplier,
                sale=None,
                purchase=purchase,
                payment_method=PaymentMethod.CASH,
                amount=purchase.paid_amount,
                date=purchase.invoice_date,
                reference_number=ref,
                status=PayStatus.COMPLETED,
                notes=PurchaseService.AUTO_PAYMENT_NOTE,
                created_by=user,
            )
            return

        qs.exclude(pk=existing.pk).delete()

        existing.customer = None
        existing.supplier = purchase.supplier
        existing.sale = None
        existing.payment_type = PaymentType.MADE
        existing.payment_method = PaymentMethod.CASH
        existing.amount = purchase.paid_amount
        existing.date = purchase.invoice_date
        existing.status = PayStatus.COMPLETED
        existing.notes = PurchaseService.AUTO_PAYMENT_NOTE
        existing.updated_by = user
        existing.save()

    @staticmethod
    def _validate_company_access(company, **kwargs):
        """
        Validate that all related objects belong to the same company.
        Prevents cross-company data access.
        """
        if 'supplier' in kwargs:
            supplier = kwargs['supplier']
            if supplier.company != company:
                raise ValidationError(
                    "Supplier does not belong to your company.")

        if 'warehouse' in kwargs:
            warehouse = kwargs['warehouse']
            if warehouse.company != company:
                raise ValidationError(
                    "Warehouse does not belong to your company.")

        if 'purchase' in kwargs:
            purchase = kwargs['purchase']
            if purchase.company != company:
                raise ValidationError(
                    "Purchase does not belong to your company.")

    @staticmethod
    def _update_stock(product, warehouse, company, quantity, unit, operation='add'):
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
        """
        # Convert quantity to base unit
        base_unit_quantity = unit.convert_to_base_unit(quantity)

        stock, _ = Stock.objects.get_or_create(
            product=product,
            warehouse=warehouse,
            company=company,
            defaults={'quantity': Decimal('0.00')}
        )

        if operation == 'add':
            stock.quantity += base_unit_quantity
        elif operation == 'subtract':
            stock.quantity -= base_unit_quantity
            # Ensure stock doesn't go negative
            if stock.quantity < 0:
                stock.quantity = Decimal('0.00')

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
    def _revert_old_items_stock(purchase, old_items, warehouse, company, should_revert_stock=True):
        """
        Revert stock for old purchase items (subtract quantities).
        Used when updating a purchase or cancelling a completed purchase.
        IMPORTANT: Converts to base unit before subtracting.

        Args:
            purchase: Purchase instance
            old_items: QuerySet of old PurchaseItem instances
            warehouse: Warehouse instance
            company: Company instance
            should_revert_stock: Boolean indicating if stock should be reverted (only if old status was completed)
        """
        for old_item in old_items:
            if old_item.quantity > 0 and should_revert_stock:
                stock, base_qty = PurchaseService._update_stock(
                    old_item.product, warehouse, company, old_item.quantity, old_item.unit, operation='subtract'
                )
                PurchaseService._create_stock_transaction(
                    product=old_item.product,
                    stock=stock,
                    unit=old_item.unit,
                    company=company,
                    original_quantity=old_item.quantity,
                    base_unit_quantity=base_qty,
                    direction=StockDirection.OUT,
                    transaction_type=TransactionType.PURCHASE_RETURN,
                    reference_id=purchase.id,
                    source_object=purchase,
                    note=f"Purchase update - reverted {old_item.quantity} {old_item.unit.name} ({base_qty} base units) from {purchase.invoice_number}",
                )

    @staticmethod
    def _process_purchase_items(purchase, items, warehouse, company, is_update=False, should_update_stock=True):
        """
        Process purchase items and optionally update stock accordingly.
        IMPORTANT: Converts all quantities to base unit before storing in stock.

        Example: If user purchases 50kg * 2 (quantity=50, unit=kg, with conversion_factor=1.0)
                 Stock will be updated by 100kg in base unit.

        Args:
            purchase: Purchase instance
            items: List of item dictionaries
            warehouse: Warehouse instance
            company: Company instance
            is_update: Boolean indicating if this is an update operation
            should_update_stock: Boolean indicating if stock should be updated (only for completed status)

        Returns:
            tuple: (purchase_items list, sub_total Decimal)
        """
        sub_total = Decimal('0.00')
        purchase_items = []

        for item in items:
            # Validate product and unit belong to the company
            product = get_object_or_404(Product.objects.filter(
                company=company), id=item['product'])
            unit = get_object_or_404(Unit.objects.filter(
                company=company), id=item['unit'])
            quantity = Decimal(str(item['quantity']))
            unit_price = Decimal(str(item['unit_price']))
            line_total = quantity * unit_price
            sub_total += line_total

            purchase_items.append(PurchaseItem(
                purchase=purchase,
                company=company,  # Automatically set company
                product=product,
                quantity=quantity,
                unit=unit,
                unit_price=unit_price,
                line_total=line_total,
            ))

            # Update stock for new items (add to stock) - CONVERTED TO BASE UNIT
            # Only update stock if should_update_stock is True (i.e., status is completed)
            if quantity > 0 and should_update_stock:
                stock, base_unit_quantity = PurchaseService._update_stock(
                    product, warehouse, company, quantity, unit, operation='add'
                )
                transaction_note = (
                    f"Purchase update - added {quantity} {unit.name} ({base_unit_quantity} base units) to {purchase.invoice_number}"
                    if is_update
                    else f"Purchase {purchase.invoice_number} - {quantity} {unit.name} = {base_unit_quantity} base units"
                )
                PurchaseService._create_stock_transaction(
                    product=product,
                    stock=stock,
                    unit=unit,
                    company=company,
                    original_quantity=quantity,
                    base_unit_quantity=base_unit_quantity,
                    direction=StockDirection.IN,
                    transaction_type=TransactionType.PURCHASE,
                    reference_id=purchase.id,
                    source_object=purchase,
                    note=transaction_note,
                )

        return purchase_items, sub_total

    @staticmethod
    def _apply_ledger_entries(purchase, company):
        """
        Apply ledger entries for a completed purchase.
        This method should only be called when purchase status is 'completed'.

        Args:
            purchase: Purchase instance
            company: Company instance
        """
        # Create ledger entries
        if purchase.grand_total > 0:
            # Create purchase ledger entry (Credit: Supplier Payable)
            LedgerService.create_purchase_ledger_entry(purchase, company)

            # Create payment ledger entry if paid_amount > 0 (Debit: Supplier Payable)
            if purchase.paid_amount > 0:
                from types import SimpleNamespace
                payment_obj = SimpleNamespace(
                    reference_number=purchase.invoice_number or f"PUR-{purchase.id}",
                    amount=purchase.paid_amount,
                    date=purchase.invoice_date,
                    notes=purchase.notes or ""
                )
                LedgerService.create_payment_ledger_entry(
                    payment_obj, company, purchase.supplier, payment_type='made', source_object=purchase)

            # Update supplier balance
            LedgerService.update_party_balance(purchase.supplier, company)

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
    def update_purchase(data, user, company):
        """
        Update an existing purchase.
        Company-aware: ensures user can only update purchases from their company.

        Args:
            data: Dictionary containing purchase data
            user: User instance
            company: Company instance from request

        Returns:
            Purchase instance
        """
        # Validate input data using serializer
        serializer = PurchaseUpdateInputSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        purchase = get_object_or_404(Purchase.objects.filter(
            company=company), id=validated_data.get("id"))
        items = validated_data.get("items")

        # Validate company access
        PurchaseService._validate_company_access(company, purchase=purchase)

        try:
            with transaction.atomic():
                # Store old status to detect transitions
                old_status = purchase.status
                old_items = list(purchase.items.all())
                warehouse = purchase.warehouse

                # Validate warehouse belongs to company
                PurchaseService._validate_company_access(
                    company, warehouse=warehouse)

                # Get new status
                new_status = validated_data.get('status', old_status)

                # Handle status transitions:
                # - If old status was completed, we need to reverse inventory/ledger
                # - If new status is completed, we need to apply inventory/ledger
                # - If old status was completed and new status is cancelled, reverse everything
                # - If old status was completed and new status is pending, reverse everything
                should_revert_old = (old_status == PurchaseStatus.COMPLETED)
                should_apply_new = (new_status == PurchaseStatus.COMPLETED)

                # Delete old ledger entries if old status was completed
                if should_revert_old:
                    LedgerService.delete_ledger_entries_for_object(
                        purchase, company)

                # Revert stock for old items only if old status was completed
                if should_revert_old:
                    PurchaseService._revert_old_items_stock(
                        purchase, old_items, warehouse, company, should_revert_stock=True)

                # Delete existing items
                purchase.items.all().delete()

                # Update purchase fields if provided
                if 'status' in validated_data:
                    purchase.status = new_status
                    # Set completed_at timestamp when status changes to completed
                    if new_status == PurchaseStatus.COMPLETED and old_status != PurchaseStatus.COMPLETED:
                        purchase.completed_at = timezone.now()
                    # Set cancelled_at timestamp when status changes to cancelled
                    elif new_status == PurchaseStatus.CANCELLED and old_status != PurchaseStatus.CANCELLED:
                        purchase.cancelled_at = timezone.now()
                if 'notes' in validated_data:
                    purchase.notes = validated_data['notes']
                purchase.updated_by = user
                purchase.save()

                # Process new items - only update stock if new status is completed
                purchase_items, sub_total = PurchaseService._process_purchase_items(
                    purchase=purchase,
                    items=items,
                    warehouse=warehouse,
                    company=company,
                    is_update=True,
                    should_update_stock=should_apply_new
                )

                PurchaseItem.objects.bulk_create(purchase_items)

                # Calculate totals
                purchase.sub_total = sub_total
                purchase.tax = Decimal(str(validated_data.get('tax', 0.00)))
                purchase.discount = Decimal(
                    str(validated_data.get('discount', 0.00)))
                purchase.delivery_charge = Decimal(
                    str(validated_data.get('delivery_charge', 0.00)))
                purchase.grand_total = sub_total + purchase.tax + \
                    purchase.delivery_charge - purchase.discount

                # Handle payment fields
                paid_amount = Decimal(
                    str(validated_data.get('paid_amount', 0.00)))
                purchase.paid_amount = paid_amount
                # Save first to ensure purchase exists for FIFO calculation
                purchase.save(update_fields=[
                              "sub_total", "tax", "discount", "delivery_charge", "grand_total", "paid_amount"])
                # Always auto-calculate payment status using FIFO formula
                PaymentFIFOService._update_invoice_payment_status(purchase, 'purchase')

                # Apply ledger entries only if new status is completed
                if should_apply_new:
                    PurchaseService._apply_ledger_entries(purchase, company)
                elif new_status in [PurchaseStatus.PENDING, PurchaseStatus.CANCELLED]:
                    # If status is pending or cancelled, ensure no ledger entries exist
                    # and update supplier balance
                    LedgerService.delete_ledger_entries_for_object(
                        purchase, company)
                    LedgerService.update_party_balance(purchase.supplier, company)

                # Sync Payment table row from paid_amount (all statuses)
                PurchaseService._sync_auto_payment_from_paid_amount(purchase, user, company)

                return purchase

        except IntegrityError as e:
            raise ValidationError(str(e))

    @staticmethod
    def create_purchase(data, user, company):
        """
        Create a new purchase.
        Company-aware: automatically sets company and validates all related objects.

        Args:
            data: Dictionary containing purchase data
            user: User instance
            company: Company instance from request

        Returns:
            Purchase instance
        """
        # Validate input data using serializer
        serializer = PurchaseCreateInputSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        warehouse = get_object_or_404(Warehouse.objects.filter(
            company=company), id=validated_data.get("warehouse"))
        supplier = get_object_or_404(Supplier.objects.filter(
            company=company), id=validated_data.get("supplier"))
        items = validated_data.get("items")

        # Validate company access for all related objects
        PurchaseService._validate_company_access(
            company, supplier=supplier, warehouse=warehouse)

        try:
            with transaction.atomic():
                # Get invoice_date from validated_data, default to today's date
                invoice_date = validated_data.get("invoice_date")
                if invoice_date is None:
                    invoice_date = timezone.now().date()

                # Generate invoice number using InvoiceNumberGenerator
                invoice_number = InvoiceNumberGenerator.generate_invoice_number(
                    company=company,
                    doc_type=DocumentType.PURCHASE_ORDER
                )

                purchase_status = validated_data.get("status", PurchaseStatus.PENDING)
                purchase = Purchase.objects.create(
                    invoice_number=invoice_number,
                    status=purchase_status,
                    created_by=user,
                    warehouse=warehouse,
                    supplier=supplier,
                    company=company,  # Automatically set company
                    notes=validated_data.get("notes", ""),
                    invoice_date=invoice_date,
                )

                # Process items - only update stock if status is completed
                should_update_stock = (purchase_status == PurchaseStatus.COMPLETED)
                purchase_items, sub_total = PurchaseService._process_purchase_items(
                    purchase=purchase,
                    items=items,
                    warehouse=warehouse,
                    company=company,
                    is_update=False,
                    should_update_stock=should_update_stock
                )

                PurchaseItem.objects.bulk_create(purchase_items)

                # Calculate totals
                purchase.sub_total = sub_total
                purchase.tax = Decimal(str(validated_data.get('tax', 0.00)))
                purchase.discount = Decimal(
                    str(validated_data.get('discount', 0.00)))
                purchase.delivery_charge = Decimal(
                    str(validated_data.get('delivery_charge', 0.00)))
                purchase.grand_total = sub_total + purchase.tax + \
                    purchase.delivery_charge - purchase.discount

                # Handle payment fields
                paid_amount = Decimal(
                    str(validated_data.get('paid_amount', 0.00)))
                purchase.paid_amount = paid_amount
                # Save first to ensure purchase exists for FIFO calculation
                purchase.save(update_fields=[
                              "sub_total", "tax", "discount", "delivery_charge", "grand_total", "paid_amount"])
                # Always auto-calculate payment status using FIFO formula
                PaymentFIFOService._update_invoice_payment_status(purchase, 'purchase')

                # Create accounting ledger entries only if status is completed
                if purchase_status == PurchaseStatus.COMPLETED:
                    PurchaseService._apply_ledger_entries(purchase, company)

                # Sync Payment table row from paid_amount (all statuses)
                PurchaseService._sync_auto_payment_from_paid_amount(purchase, user, company)

                return purchase

        except IntegrityError as e:
            raise ValidationError(str(e))
