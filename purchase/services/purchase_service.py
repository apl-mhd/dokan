from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from inventory.models import Stock, StockTransaction, TransactionType, StockDirection
from product.models import Product, Unit
from purchase.models import Purchase, PurchaseItem, PurchaseStatus
from supplier.models import Supplier
from warehouse.models import Warehouse
from purchase.serializers import (
    PurchaseCreateInputSerializer,
    PurchaseUpdateInputSerializer
)
from rest_framework.exceptions import ValidationError
from uuid import uuid4


class PurchaseService:

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
    def _revert_old_items_stock(purchase, old_items, warehouse, company):
        """
        Revert stock for old purchase items (subtract quantities).
        Used when updating a purchase.
        IMPORTANT: Converts to base unit before subtracting.

        Args:
            purchase: Purchase instance
            old_items: QuerySet of old PurchaseItem instances
            warehouse: Warehouse instance
            company: Company instance
        """
        for old_item in old_items:
            if old_item.quantity > 0:
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
                    note=f"Purchase update - reverted {old_item.quantity} {old_item.unit.name} ({base_qty} base units) from {purchase.invoice_number}",
                )

    @staticmethod
    def _process_purchase_items(purchase, items, warehouse, company, is_update=False):
        """
        Process purchase items and update stock accordingly.
        IMPORTANT: Converts all quantities to base unit before storing in stock.
        
        Example: If user purchases 50kg * 2 (quantity=50, unit=kg, with conversion_factor=1.0)
                 Stock will be updated by 100kg in base unit.

        Args:
            purchase: Purchase instance
            items: List of item dictionaries
            warehouse: Warehouse instance
            company: Company instance
            is_update: Boolean indicating if this is an update operation

        Returns:
            tuple: (purchase_items list, grand_total Decimal)
        """
        grand_total = Decimal('0.00')
        purchase_items = []

        for item in items:
            product = get_object_or_404(Product, id=item['product'])
            unit = get_object_or_404(Unit, id=item['unit'])
            quantity = Decimal(str(item['quantity']))
            unit_price = Decimal(str(item['unit_price']))
            line_total = quantity * unit_price
            grand_total += line_total

            purchase_items.append(PurchaseItem(
                purchase=purchase,
                company=company,  # Automatically set company
                product=product,
                quantity=quantity,
                unit=unit,
                unit_price=unit_price,
                line_total=line_total,
            ))

            # Update stock for new items - CONVERTED TO BASE UNIT
            if quantity > 0:
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
                    note=transaction_note,
                )

        return purchase_items, grand_total

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
                # Get old items before deleting for stock adjustment
                old_items = list(purchase.items.all())
                warehouse = purchase.warehouse

                # Validate warehouse belongs to company
                PurchaseService._validate_company_access(
                    company, warehouse=warehouse)

                # Revert stock for old items first
                PurchaseService._revert_old_items_stock(
                    purchase, old_items, warehouse, company)

                # Delete existing items
                purchase.items.all().delete()

                # Update purchase fields if provided
                if 'status' in validated_data:
                    purchase.status = validated_data['status']
                if 'notes' in validated_data:
                    purchase.notes = validated_data['notes']
                purchase.updated_by = user
                purchase.save()

                # Process new items and update stock
                purchase_items, grand_total = PurchaseService._process_purchase_items(
                    purchase=purchase,
                    items=items,
                    warehouse=warehouse,
                    company=company,
                    is_update=True
                )

                PurchaseItem.objects.bulk_create(purchase_items)
                purchase.grand_total = grand_total
                purchase.save(update_fields=["grand_total"])

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
                purchase = Purchase.objects.create(
                    invoice_number=str(uuid4()),
                    status=validated_data.get(
                        "status", PurchaseStatus.PENDING),
                    created_by=user,
                    warehouse=warehouse,
                    supplier=supplier,
                    company=company,  # Automatically set company
                    notes=validated_data.get("notes", ""),
                    invoice_date=validated_data.get("invoice_date"),
                )

                # Process items and update stock
                purchase_items, grand_total = PurchaseService._process_purchase_items(
                    purchase=purchase,
                    items=items,
                    warehouse=warehouse,
                    company=company,
                    is_update=False
                )

                PurchaseItem.objects.bulk_create(purchase_items)
                purchase.grand_total = grand_total
                purchase.save(update_fields=["grand_total"])

                return purchase

        except IntegrityError as e:
            raise ValidationError(str(e))
