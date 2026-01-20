from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from inventory.models import Stock, StockTransaction, TransactionType, StockDirection
from product.models import Product, Unit
from purchase.models import (
    Purchase, PurchaseItem, PurchaseReturn, PurchaseReturnItem,
    PurchaseReturnStatus, PurchaseStatus
)
from supplier.models import Supplier
from warehouse.models import Warehouse
from core.services.invoice_number import InvoiceNumberGenerator
from core.models import DocumentType
from accounting.services.ledger_service import LedgerService


class PurchaseReturnService:
    """Service class for handling purchase return operations"""
    MONEY_QUANT = Decimal('0.01')

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        """Quantize monetary values to 2 decimal places."""
        if value is None:
            return Decimal('0.00')
        return Decimal(value).quantize(PurchaseReturnService.MONEY_QUANT, rounding=ROUND_HALF_UP)

    @staticmethod
    def _validate_company_access(company, **kwargs):
        """
        Validate that all related objects belong to the same company.
        Prevents cross-company data access.
        """
        if 'purchase' in kwargs:
            purchase = kwargs['purchase']
            if purchase.company != company:
                raise ValidationError(
                    "Purchase does not belong to your company.")

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

        if 'purchase_return' in kwargs:
            purchase_return = kwargs['purchase_return']
            if purchase_return.company != company:
                raise ValidationError(
                    "Purchase return does not belong to your company.")

    @staticmethod
    def _validate_purchase_for_return(purchase):
        """
        Validate that a purchase can have items returned.

        Args:
            purchase: Purchase instance

        Raises:
            ValidationError: If purchase cannot have returns
        """
        # Purchase must be completed to be returned
        # Note: comparing string values, not enum values
        if purchase.status != 'completed':
            raise ValidationError(
                f"Cannot create return for purchase with status '{purchase.status}'. "
                "Only completed purchases can be returned."
            )

    @staticmethod
    def _validate_return_quantity(purchase_item, requested_quantity):
        """
        Validate that return quantity doesn't exceed available quantity.

        Args:
            purchase_item: PurchaseItem instance
            requested_quantity: Decimal quantity to return

        Returns:
            Decimal: Total already returned quantity

        Raises:
            ValidationError: If return quantity exceeds available
        """
        # For purchase returns, we check against the original purchase item
        # We don't track per-item returns in this simplified version
        available_to_return = purchase_item.quantity

        if requested_quantity > available_to_return:
            raise ValidationError(
                f"Cannot return {requested_quantity} units of {purchase_item.product.name}. "
                f"Original purchase quantity: {purchase_item.quantity}"
            )

    @staticmethod
    def _update_stock(product, warehouse, quantity, unit, company, direction=StockDirection.OUT):
        """
        Update stock levels for returned product.

        Args:
            product: Product instance
            warehouse: Warehouse instance
            quantity: Decimal quantity to adjust
            unit: Unit instance
            company: Company instance
            direction: StockDirection (OUT for returns, IN for cancellations)
        """
        # Convert quantity to base unit (Stock.quantity is stored in base units)
        base_unit_quantity = unit.convert_to_base_unit(quantity)

        # Get or create stock record
        stock, created = Stock.objects.get_or_create(
            company=company,
            product=product,
            warehouse=warehouse,
            defaults={'quantity': Decimal('0.00')}
        )

        # Update quantity (subtract for returns)
        if direction == StockDirection.OUT:
            stock.quantity -= base_unit_quantity
            # Keep consistent with PurchaseService behavior: don't allow negative stock
            if stock.quantity < 0:
                stock.quantity = Decimal('0.00')
        else:
            stock.quantity += base_unit_quantity

        stock.save(update_fields=["quantity"])

        return stock, base_unit_quantity

    @staticmethod
    def _create_stock_transaction(
        product,
        stock,
        unit,
        company,
        original_quantity,
        base_unit_quantity,
        direction,
        transaction_type,
        reference_id,
        note=None,
        source_object=None
    ):
        """
        Create stock transaction record for audit trail.

        Args:
            product: Product instance
            stock: Stock instance
            unit: Unit instance
            company: Company instance
            original_quantity: Decimal quantity in original unit
            base_unit_quantity: Decimal quantity in base unit (stored in Stock)
            direction: StockDirection.IN or StockDirection.OUT
            transaction_type: TransactionType enum value
            reference_id: related object id
            note: Optional note string
        """
        from django.contrib.contenttypes.models import ContentType

        content_type = None
        object_id = None
        if source_object is not None:
            content_type = ContentType.objects.get_for_model(source_object.__class__)
            object_id = source_object.id

        StockTransaction.objects.create(
            company=company,
            product=product,
            stock=stock,
            unit=unit,
            quantity=base_unit_quantity,  # store base unit quantity for consistency
            transaction_type=transaction_type,
            direction=direction,
            reference_id=reference_id,
            content_type=content_type,
            object_id=object_id,
            balance_after=stock.quantity,
            note=note or f"Original: {original_quantity} {unit.name} = {base_unit_quantity} base units"
        )

    @staticmethod
    def _generate_return_number(company):
        """Generate unique return number"""
        return InvoiceNumberGenerator.generate_invoice_number(
            company=company,
            doc_type=DocumentType.PURCHASE_RETURN
        )

    @staticmethod
    def _calculate_line_total(quantity, unit_price):
        """Calculate line total"""
        return PurchaseReturnService._money(Decimal(quantity) * Decimal(unit_price))

    @staticmethod
    def _calculate_return_totals(items_data):
        """
        Calculate return totals from items data.

        Args:
            items_data: List of dicts with quantity and unit_price

        Returns:
            dict: Contains sub_total, tax, discount, grand_total
        """
        sub_total = sum(
            PurchaseReturnService._calculate_line_total(
                Decimal(str(item['quantity'])),
                Decimal(str(item['unit_price']))
            )
            for item in items_data
        )
        sub_total = PurchaseReturnService._money(sub_total)

        # For now, use same tax/discount as original purchase or default to 0
        tax = PurchaseReturnService._money(Decimal('0.00'))
        discount = PurchaseReturnService._money(Decimal('0.00'))
        grand_total = PurchaseReturnService._money(sub_total + tax - discount)

        return {
            'sub_total': sub_total,
            'tax': tax,
            'discount': discount,
            'grand_total': grand_total
        }

    @staticmethod
    @transaction.atomic
    def create_purchase_return(data, company, user):
        """
        Create a new purchase return with items.

        Args:
            data: Dict containing return data and items
            company: Company instance
            user: User instance creating the return

        Returns:
            PurchaseReturn: Created purchase return instance
        """
        # Get and validate related objects
        purchase = get_object_or_404(
            Purchase.objects.filter(company=company),
            id=data['purchase_id']
        )
        supplier = purchase.supplier
        warehouse = get_object_or_404(
            Warehouse.objects.filter(company=company),
            id=data.get('warehouse_id', purchase.warehouse.id)
        )

        # Validate company access
        PurchaseReturnService._validate_company_access(
            company,
            purchase=purchase,
            supplier=supplier,
            warehouse=warehouse
        )

        # Validate purchase can be returned
        PurchaseReturnService._validate_purchase_for_return(purchase)

        # Calculate totals
        items_data = data.get('items', [])
        if not items_data:
            raise ValidationError("At least one item is required for return.")

        totals = PurchaseReturnService._calculate_return_totals(items_data)

        # Generate return number
        return_number = PurchaseReturnService._generate_return_number(company)

        # Get return status from data or default to pending
        return_status = data.get('status', PurchaseReturnStatus.PENDING)

        # Create purchase return
        purchase_return = PurchaseReturn.objects.create(
            purchase=purchase,
            company=company,
            supplier=supplier,
            warehouse=warehouse,
            return_number=return_number,
            return_date=data.get('return_date', timezone.now()),
            sub_total=totals['sub_total'],
            tax=totals['tax'],
            discount=totals['discount'],
            grand_total=totals['grand_total'],
            refund_amount=PurchaseReturnService._money(
                Decimal(str(data.get('refund_amount', totals['grand_total'])))
            ),
            status=return_status,
            reason=data.get('reason', ''),
            notes=data.get('notes', ''),
            created_by=user
        )

        # Set completed_at if status is completed
        if return_status == PurchaseReturnStatus.COMPLETED:
            purchase_return.completed_at = timezone.now()
            purchase_return.save()

        # Process return items
        for item_data in items_data:
            PurchaseReturnService._process_return_item(
                purchase_return=purchase_return,
                item_data=item_data,
                company=company,
                user=user,
                should_update_stock=(
                    return_status == PurchaseReturnStatus.COMPLETED)
            )

        # Create ledger entries if completed
        if return_status == PurchaseReturnStatus.COMPLETED:
            PurchaseReturnService._apply_ledger_entries(
                purchase_return, company
            )

        return purchase_return

    @staticmethod
    def _process_return_item(purchase_return, item_data, company, user, should_update_stock=True):
        """
        Process a single return item.

        Args:
            purchase_return: PurchaseReturn instance
            item_data: Dict containing item details
            company: Company instance
            user: User instance
            should_update_stock: Boolean whether to update stock
        """
        product = get_object_or_404(
            Product.objects.filter(company=company),
            id=item_data['product_id']
        )
        unit = get_object_or_404(
            Unit.objects.all(),
            id=item_data['unit_id']
        )

        quantity = Decimal(str(item_data['quantity']))
        unit_price = Decimal(str(item_data['unit_price']))
        line_total = PurchaseReturnService._calculate_line_total(
            quantity, unit_price)

        # Create return item
        return_item = PurchaseReturnItem.objects.create(
            purchase_return=purchase_return,
            company=company,
            product=product,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
            line_total=line_total,
            reason=item_data.get('reason', '')
        )

        # Update stock and create transaction if completed
        if should_update_stock:
            # Subtract from stock (we're returning/removing items)
            stock, base_qty = PurchaseReturnService._update_stock(
                product=product,
                warehouse=purchase_return.warehouse,
                quantity=quantity,
                unit=unit,
                company=company,
                direction=StockDirection.OUT
            )

            # Create stock transaction
            PurchaseReturnService._create_stock_transaction(
                product=product,
                stock=stock,
                unit=unit,
                company=company,
                original_quantity=quantity,
                base_unit_quantity=base_qty,
                direction=StockDirection.OUT,
                transaction_type=TransactionType.PURCHASE_RETURN,
                reference_id=purchase_return.id,
                source_object=purchase_return,
                note=(
                    f"Purchase Return {purchase_return.return_number or f'PRET-{purchase_return.id}'} - "
                    f"{quantity} {unit.name} = {base_qty} base units"
                )
            )

        return return_item

    @staticmethod
    def _apply_ledger_entries(purchase_return, company):
        """
        Create ledger entries for completed purchase return.

        Args:
            purchase_return: PurchaseReturn instance
            company: Company instance
        """
        if purchase_return.grand_total > 0:
            LedgerService.create_purchase_return_ledger_entry(
                purchase_return, company
            )
            # Update supplier balance
            LedgerService.update_party_balance(
                purchase_return.supplier, company
            )

    @staticmethod
    @transaction.atomic
    def complete_purchase_return(purchase_return_id, company, user):
        """
        Complete a pending purchase return.

        Args:
            purchase_return_id: ID of purchase return
            company: Company instance
            user: User instance

        Returns:
            PurchaseReturn: Updated purchase return instance
        """
        purchase_return = get_object_or_404(
            PurchaseReturn.objects.filter(company=company),
            id=purchase_return_id
        )

        # Validate company access
        PurchaseReturnService._validate_company_access(
            company,
            purchase_return=purchase_return
        )

        # Can only complete pending returns
        if purchase_return.status != PurchaseReturnStatus.PENDING:
            raise ValidationError(
                f"Cannot complete return with status '{purchase_return.status}'. "
                "Only pending returns can be completed."
            )

        # Update status
        purchase_return.status = PurchaseReturnStatus.COMPLETED
        purchase_return.completed_at = timezone.now()
        purchase_return.updated_by = user
        purchase_return.save()

        # Update stock for all items
        for return_item in purchase_return.items.all():
            # Subtract from stock
            stock, base_qty = PurchaseReturnService._update_stock(
                product=return_item.product,
                warehouse=purchase_return.warehouse,
                quantity=return_item.quantity,
                unit=return_item.unit,
                company=company,
                direction=StockDirection.OUT
            )

            # Create stock transaction
            PurchaseReturnService._create_stock_transaction(
                product=return_item.product,
                stock=stock,
                unit=return_item.unit,
                company=company,
                original_quantity=return_item.quantity,
                base_unit_quantity=base_qty,
                direction=StockDirection.OUT,
                transaction_type=TransactionType.PURCHASE_RETURN,
                reference_id=purchase_return.id,
                source_object=purchase_return,
                note=(
                    f"Purchase Return complete {purchase_return.return_number or f'PRET-{purchase_return.id}'} - "
                    f"{return_item.quantity} {return_item.unit.name} = {base_qty} base units"
                )
            )

        # Create ledger entries
        PurchaseReturnService._apply_ledger_entries(purchase_return, company)

        return purchase_return

    @staticmethod
    @transaction.atomic
    def cancel_purchase_return(purchase_return_id, company, user):
        """
        Cancel a purchase return.

        Args:
            purchase_return_id: ID of purchase return
            company: Company instance
            user: User instance

        Returns:
            PurchaseReturn: Cancelled purchase return instance
        """
        purchase_return = get_object_or_404(
            PurchaseReturn.objects.filter(company=company),
            id=purchase_return_id
        )

        # Validate company access
        PurchaseReturnService._validate_company_access(
            company,
            purchase_return=purchase_return
        )

        # Can only cancel pending or completed returns
        if purchase_return.status == PurchaseReturnStatus.CANCELLED:
            raise ValidationError("Return is already cancelled.")

        # If completed, need to reverse stock and ledger
        if purchase_return.status == PurchaseReturnStatus.COMPLETED:
            # Reverse stock changes (add back)
            for return_item in purchase_return.items.all():
                stock, base_qty = PurchaseReturnService._update_stock(
                    product=return_item.product,
                    warehouse=purchase_return.warehouse,
                    quantity=return_item.quantity,
                    unit=return_item.unit,
                    company=company,
                    direction=StockDirection.IN  # Add back
                )

                # Create reversal transaction
                PurchaseReturnService._create_stock_transaction(
                    product=return_item.product,
                    stock=stock,
                    unit=return_item.unit,
                    company=company,
                    original_quantity=return_item.quantity,
                    base_unit_quantity=base_qty,
                    direction=StockDirection.IN,  # Add back
                    transaction_type=TransactionType.PURCHASE_RETURN,
                    reference_id=purchase_return.id,
                    source_object=purchase_return,
                    note=(
                        f"Purchase Return cancel {purchase_return.return_number or f'PRET-{purchase_return.id}'} - "
                        f"reverted {return_item.quantity} {return_item.unit.name} = {base_qty} base units"
                    )
                )

            # Delete ledger entries
            LedgerService.delete_ledger_entries_for_object(
                purchase_return, company)
            # Update supplier balance
            LedgerService.update_party_balance(
                purchase_return.supplier, company)

        # Update status
        purchase_return.status = PurchaseReturnStatus.CANCELLED
        purchase_return.cancelled_at = timezone.now()
        purchase_return.updated_by = user
        purchase_return.save()

        return purchase_return

    @staticmethod
    def get_returnable_items(purchase_id, company):
        """
        Get list of items that can still be returned from a purchase.

        Args:
            purchase_id: ID of the purchase
            company: Company instance

        Returns:
            List of dictionaries with item info and returnable quantity
        """
        purchase = get_object_or_404(
            Purchase.objects.filter(company=company),
            id=purchase_id
        )

        # Validate company access
        PurchaseReturnService._validate_company_access(
            company, purchase=purchase)

        # Validate purchase can be returned
        PurchaseReturnService._validate_purchase_for_return(purchase)

        returnable_items = []

        for purchase_item in purchase.items.all():
            # Calculate already returned quantity for this product from this purchase
            # Since PurchaseReturnItem doesn't have purchase_item FK, we filter by product and purchase_return's purchase
            existing_returns = PurchaseReturnItem.objects.filter(
                company=company,
                product=purchase_item.product,
                purchase_return__purchase=purchase,
                purchase_return__status__in=['pending', 'completed']
            )

            total_returned = sum(
                item.quantity for item in existing_returns
            ) if existing_returns.exists() else Decimal('0.00')

            available_to_return = purchase_item.quantity - total_returned

            if available_to_return > 0:
                returnable_items.append({
                    'purchase_item_id': purchase_item.id,
                    'product_id': purchase_item.product.id,
                    'product_name': purchase_item.product.name,
                    'original_quantity': float(purchase_item.quantity),
                    'returned_quantity': float(total_returned),
                    'available_to_return': float(available_to_return),
                    'unit_id': purchase_item.unit.id,
                    'unit_name': purchase_item.unit.name,
                    'unit_price': float(purchase_item.unit_price),
                    'line_total': float(purchase_item.line_total),
                })

        return returnable_items
