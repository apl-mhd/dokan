from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from inventory.models import Stock, StockTransaction, TransactionType, StockDirection
from product.models import Product, Unit
from sale.models import (
    Sale, SaleItem, SaleReturn, SaleReturnItem, 
    SaleReturnStatus, RefundStatus, SaleStatus
)
from customer.models import Customer
from warehouse.models import Warehouse
from core.services.invoice_number import InvoiceNumberGenerator
from core.models import DocumentType
from accounting.services.ledger_service import LedgerService


class SaleReturnService:
    """Service class for handling sale return operations"""

    @staticmethod
    def _validate_company_access(company, **kwargs):
        """
        Validate that all related objects belong to the same company.
        Prevents cross-company data access.
        """
        if 'sale' in kwargs:
            sale = kwargs['sale']
            if sale.company != company:
                raise ValidationError("Sale does not belong to your company.")

        if 'customer' in kwargs:
            customer = kwargs['customer']
            if customer.company != company:
                raise ValidationError("Customer does not belong to your company.")

        if 'warehouse' in kwargs:
            warehouse = kwargs['warehouse']
            if warehouse.company != company:
                raise ValidationError("Warehouse does not belong to your company.")

        if 'sale_return' in kwargs:
            sale_return = kwargs['sale_return']
            if sale_return.company != company:
                raise ValidationError("Sale return does not belong to your company.")

    @staticmethod
    def _validate_sale_for_return(sale):
        """
        Validate that a sale can have items returned.
        
        Args:
            sale: Sale instance
            
        Raises:
            ValidationError: If sale cannot have returns
        """
        # Sale must be delivered to be returned
        if sale.status != SaleStatus.DELIVERED:
            raise ValidationError(
                f"Cannot create return for sale with status '{sale.status}'. "
                "Only delivered sales can be returned."
            )

    @staticmethod
    def _validate_return_quantity(sale_item, requested_quantity):
        """
        Validate that return quantity doesn't exceed available quantity.
        
        Args:
            sale_item: SaleItem instance
            requested_quantity: Decimal quantity to return
            
        Returns:
            Decimal: Total already returned quantity
            
        Raises:
            ValidationError: If return quantity exceeds available
        """
        # Get total already returned for this sale item
        existing_returns = SaleReturnItem.objects.filter(
            sale_item=sale_item,
            sale_return__status__in=[SaleReturnStatus.PENDING, SaleReturnStatus.COMPLETED]
        )
        
        total_returned = sum(
            item.returned_quantity for item in existing_returns
        ) if existing_returns.exists() else Decimal('0.00')
        
        available_to_return = sale_item.quantity - total_returned
        
        if requested_quantity > available_to_return:
            raise ValidationError(
                f"Cannot return {requested_quantity} units of {sale_item.product.name}. "
                f"Original quantity: {sale_item.quantity}, "
                f"Already returned: {total_returned}, "
                f"Available to return: {available_to_return}"
            )
        
        return total_returned

    @staticmethod
    def _update_stock(product, warehouse, company, quantity, unit, operation='add'):
        """
        Update stock quantity for a returned product.
        For returns, we typically ADD stock back.
        Converts quantity to base unit before storing.
        
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
            if stock.quantity < base_unit_quantity:
                base_unit_name = product.base_unit.name if product.base_unit else "base units"
                raise ValidationError(
                    f"Insufficient stock for {product.name}. "
                    f"Available: {stock.quantity} {base_unit_name}"
                )
            stock.quantity -= base_unit_quantity
        
        stock.save(update_fields=["quantity"])
        return stock, base_unit_quantity

    @staticmethod
    def _create_stock_transaction(product, stock, unit, company, original_quantity, 
                                  base_unit_quantity, direction, reference_id, note=None, source_object=None):
        """
        Create a stock transaction record for sale return.
        
        Args:
            product: Product instance
            stock: Stock instance
            unit: Unit instance
            company: Company instance
            original_quantity: Decimal quantity in original unit
            base_unit_quantity: Decimal quantity in base unit
            direction: StockDirection.IN or StockDirection.OUT
            reference_id: SaleReturn ID
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
            quantity=base_unit_quantity,
            stock=stock,
            unit=unit,
            company=company,
            direction=direction,
            transaction_type=TransactionType.SALE_RETURN,
            reference_id=reference_id,
            content_type=content_type,
            object_id=object_id,
            balance_after=stock.quantity,
            note=note or f"Return: {original_quantity} {unit.name} = {base_unit_quantity} base units",
        )
        return stock_transaction

    @staticmethod
    def _calculate_refund_status(refunded_amount, grand_total):
        """Calculate refund status based on refunded_amount and grand_total"""
        if refunded_amount <= 0:
            return RefundStatus.NOT_REFUNDED
        elif refunded_amount >= grand_total:
            return RefundStatus.REFUNDED
        else:
            return RefundStatus.PARTIAL

    @staticmethod
    def _process_return_items(sale_return, items, sale, company):
        """
        Process and validate return items.
        
        Args:
            sale_return: SaleReturn instance
            items: List of item dictionaries with sale_item_id, quantity, condition
            sale: Sale instance
            company: Company instance
            
        Returns:
            tuple: (return_items list, sub_total Decimal)
        """
        sub_total = Decimal('0.00')
        return_items = []
        
        for item_data in items:
            # Get the original sale item
            sale_item = get_object_or_404(
                SaleItem.objects.filter(sale=sale, company=company),
                id=item_data['sale_item_id']
            )
            
            returned_quantity = Decimal(str(item_data['returned_quantity']))
            
            # Validate return quantity
            SaleReturnService._validate_return_quantity(sale_item, returned_quantity)
            
            # Calculate line total using original sale price
            line_total = returned_quantity * sale_item.unit_price
            sub_total += line_total
            
            return_items.append(SaleReturnItem(
                sale_return=sale_return,
                sale_item=sale_item,
                company=company,
                product=sale_item.product,
                returned_quantity=returned_quantity,
                unit=sale_item.unit,
                unit_price=sale_item.unit_price,
                line_total=line_total,
                condition=item_data.get('condition', 'good'),
                condition_notes=item_data.get('condition_notes', ''),
            ))
        
        return return_items, sub_total

    @staticmethod
    def _apply_stock_updates(sale_return, warehouse, company):
        """
        Apply stock updates for completed sale return.
        Adds returned items back to inventory.
        
        Args:
            sale_return: SaleReturn instance
            warehouse: Warehouse instance
            company: Company instance
        """
        for return_item in sale_return.items.all():
            # Only add stock back if item is in good condition or can be resold
            # You might want to customize this based on business rules
            should_restock = return_item.condition in ['good', 'wrong_item']
            
            if should_restock:
                stock, base_qty = SaleReturnService._update_stock(
                    product=return_item.product,
                    warehouse=warehouse,
                    company=company,
                    quantity=return_item.returned_quantity,
                    unit=return_item.unit,
                    operation='add'
                )
                
                SaleReturnService._create_stock_transaction(
                    product=return_item.product,
                    stock=stock,
                    unit=return_item.unit,
                    company=company,
                    original_quantity=return_item.returned_quantity,
                    base_unit_quantity=base_qty,
                    direction=StockDirection.IN,
                    reference_id=sale_return.id,
                    source_object=sale_return,
                    note=f"Sale return {sale_return.return_number} - {return_item.returned_quantity} {return_item.unit.name} ({base_qty} base units) - Condition: {return_item.condition}"
                )

    @staticmethod
    def _apply_ledger_entries(sale_return, company):
        """
        Apply ledger entries for completed sale return.
        Creates reverse entries to offset the original sale.
        
        Args:
            sale_return: SaleReturn instance
            company: Company instance
        """
        if sale_return.grand_total > 0:
            # Create return ledger entry (Credit: Customer Receivable - reduces what customer owes)
            LedgerService.create_sale_return_ledger_entry(sale_return, company)
            
            # If refund was given, record it (Debit: Customer Receivable - money returned)
            if sale_return.refunded_amount > 0:
                from types import SimpleNamespace
                refund_obj = SimpleNamespace(
                    reference_number=sale_return.return_number or f"RET-{sale_return.id}",
                    amount=sale_return.refunded_amount,
                    date=sale_return.return_date,
                    notes=sale_return.notes or ""
                )
                LedgerService.create_payment_ledger_entry(
                    refund_obj, company, sale_return.customer, 
                    payment_type='paid', source_object=sale_return
                )
            
            # Update customer balance
            LedgerService.update_party_balance(sale_return.customer, company)

    @staticmethod
    def create_sale_return(data, user, company):
        """
        Create a new sale return.
        
        Args:
            data: Dictionary containing:
                - sale_id: ID of the original sale
                - return_date: Date of return
                - return_reason: Reason for return
                - items: List of items being returned
                - tax: Tax amount (optional)
                - discount: Discount amount (optional)
                - refunded_amount: Amount refunded to customer (optional)
                - notes: Additional notes (optional)
            user: User instance
            company: Company instance
            
        Returns:
            SaleReturn instance
        """
        try:
            with transaction.atomic():
                # Get and validate the original sale
                sale = get_object_or_404(
                    Sale.objects.filter(company=company),
                    id=data['sale_id']
                )
                
                # Validate company access
                SaleReturnService._validate_company_access(
                    company, 
                    sale=sale,
                    customer=sale.customer,
                    warehouse=sale.warehouse
                )
                
                # Validate sale can be returned
                SaleReturnService._validate_sale_for_return(sale)
                
                # Generate return number
                return_number = InvoiceNumberGenerator.generate_invoice_number(
                    company=company,
                    doc_type=DocumentType.SALES_RETURN
                )
                
                # Create sale return
                sale_return = SaleReturn.objects.create(
                    sale=sale,
                    customer=sale.customer,
                    company=company,
                    warehouse=sale.warehouse,
                    return_number=return_number,
                    return_date=data.get('return_date', timezone.now().date()),
                    return_reason=data['return_reason'],
                    notes=data.get('notes', ''),
                    status=SaleReturnStatus.PENDING,
                    created_by=user
                )
                
                # Process return items
                return_items, sub_total = SaleReturnService._process_return_items(
                    sale_return=sale_return,
                    items=data['items'],
                    sale=sale,
                    company=company
                )
                
                # Bulk create return items
                SaleReturnItem.objects.bulk_create(return_items)
                
                # Calculate totals
                sale_return.sub_total = sub_total
                sale_return.tax = Decimal(str(data.get('tax', 0.00)))
                sale_return.discount = Decimal(str(data.get('discount', 0.00)))
                sale_return.grand_total = sub_total + sale_return.tax - sale_return.discount
                
                # Handle refund
                refunded_amount = Decimal(str(data.get('refunded_amount', 0.00)))
                sale_return.refunded_amount = refunded_amount
                sale_return.refund_status = SaleReturnService._calculate_refund_status(
                    refunded_amount, sale_return.grand_total
                )
                
                sale_return.save(update_fields=[
                    "sub_total", "tax", "discount", "grand_total", 
                    "refunded_amount", "refund_status"
                ])
                
                return sale_return
                
        except DjangoValidationError as e:
            raise ValidationError(str(e))

    @staticmethod
    def update_sale_return(data, user, company):
        """
        Update an existing sale return.
        Can only update returns that are in PENDING status.
        
        Args:
            data: Dictionary containing return data including 'id'
            user: User instance
            company: Company instance
            
        Returns:
            SaleReturn instance
        """
        try:
            with transaction.atomic():
                sale_return = get_object_or_404(
                    SaleReturn.objects.filter(company=company),
                    id=data['id']
                )
                
                # Validate company access
                SaleReturnService._validate_company_access(
                    company, sale_return=sale_return
                )
                
                # Can only update pending returns
                if sale_return.status != SaleReturnStatus.PENDING:
                    raise ValidationError(
                        f"Cannot update sale return with status '{sale_return.status}'. "
                        "Only pending returns can be updated."
                    )
                
                # Delete existing items
                sale_return.items.all().delete()
                
                # Process new items
                return_items, sub_total = SaleReturnService._process_return_items(
                    sale_return=sale_return,
                    items=data['items'],
                    sale=sale_return.sale,
                    company=company
                )
                
                # Bulk create new items
                SaleReturnItem.objects.bulk_create(return_items)
                
                # Update fields
                if 'return_reason' in data:
                    sale_return.return_reason = data['return_reason']
                if 'notes' in data:
                    sale_return.notes = data['notes']
                if 'return_date' in data:
                    sale_return.return_date = data['return_date']
                
                # Recalculate totals
                sale_return.sub_total = sub_total
                sale_return.tax = Decimal(str(data.get('tax', 0.00)))
                sale_return.discount = Decimal(str(data.get('discount', 0.00)))
                sale_return.grand_total = sub_total + sale_return.tax - sale_return.discount
                
                # Update refund
                refunded_amount = Decimal(str(data.get('refunded_amount', 0.00)))
                sale_return.refunded_amount = refunded_amount
                sale_return.refund_status = SaleReturnService._calculate_refund_status(
                    refunded_amount, sale_return.grand_total
                )
                
                sale_return.updated_by = user
                sale_return.save()
                
                return sale_return
                
        except DjangoValidationError as e:
            raise ValidationError(str(e))

    @staticmethod
    def complete_sale_return(sale_return_id, user, company):
        """
        Complete a sale return.
        This will:
        1. Update inventory (add items back to stock)
        2. Create accounting ledger entries
        3. Update customer balance
        
        Args:
            sale_return_id: ID of the sale return
            user: User instance
            company: Company instance
            
        Returns:
            SaleReturn instance
        """
        try:
            with transaction.atomic():
                sale_return = get_object_or_404(
                    SaleReturn.objects.filter(company=company),
                    id=sale_return_id
                )
                
                # Validate company access
                SaleReturnService._validate_company_access(
                    company, sale_return=sale_return
                )
                
                # Can only complete pending returns
                if sale_return.status != SaleReturnStatus.PENDING:
                    raise ValidationError(
                        f"Cannot complete sale return with status '{sale_return.status}'. "
                        "Only pending returns can be completed."
                    )
                
                # Apply stock updates
                SaleReturnService._apply_stock_updates(
                    sale_return, sale_return.warehouse, company
                )
                
                # Apply ledger entries
                SaleReturnService._apply_ledger_entries(sale_return, company)
                
                # Update status
                sale_return.status = SaleReturnStatus.COMPLETED
                sale_return.completed_at = timezone.now()
                sale_return.updated_by = user
                sale_return.save(update_fields=['status', 'completed_at', 'updated_by', 'updated_at'])
                
                return sale_return
                
        except DjangoValidationError as e:
            raise ValidationError(str(e))

    @staticmethod
    def cancel_sale_return(sale_return_id, user, company):
        """
        Cancel a sale return.
        Can only cancel pending returns.
        
        Args:
            sale_return_id: ID of the sale return
            user: User instance
            company: Company instance
            
        Returns:
            SaleReturn instance
        """
        try:
            with transaction.atomic():
                sale_return = get_object_or_404(
                    SaleReturn.objects.filter(company=company),
                    id=sale_return_id
                )
                
                # Validate company access
                SaleReturnService._validate_company_access(
                    company, sale_return=sale_return
                )
                
                # Can only cancel pending returns
                if sale_return.status != SaleReturnStatus.PENDING:
                    raise ValidationError(
                        f"Cannot cancel sale return with status '{sale_return.status}'. "
                        "Only pending returns can be cancelled."
                    )
                
                # Update status
                sale_return.status = SaleReturnStatus.CANCELLED
                sale_return.cancelled_at = timezone.now()
                sale_return.updated_by = user
                sale_return.save(update_fields=['status', 'cancelled_at', 'updated_by', 'updated_at'])
                
                return sale_return
                
        except DjangoValidationError as e:
            raise ValidationError(str(e))

    @staticmethod
    def get_returnable_items(sale_id, company):
        """
        Get list of items that can still be returned from a sale.
        
        Args:
            sale_id: ID of the sale
            company: Company instance
            
        Returns:
            List of dictionaries with item info and returnable quantity
        """
        sale = get_object_or_404(
            Sale.objects.filter(company=company),
            id=sale_id
        )
        
        # Validate company access
        SaleReturnService._validate_company_access(company, sale=sale)
        
        # Validate sale can be returned
        SaleReturnService._validate_sale_for_return(sale)
        
        returnable_items = []
        
        for sale_item in sale.items.all():
            # Calculate already returned quantity
            existing_returns = SaleReturnItem.objects.filter(
                sale_item=sale_item,
                sale_return__status__in=[SaleReturnStatus.PENDING, SaleReturnStatus.COMPLETED]
            )
            
            total_returned = sum(
                item.returned_quantity for item in existing_returns
            ) if existing_returns.exists() else Decimal('0.00')
            
            available_to_return = sale_item.quantity - total_returned
            
            if available_to_return > 0:
                returnable_items.append({
                    'sale_item_id': sale_item.id,
                    'product_id': sale_item.product.id,
                    'product_name': sale_item.product.name,
                    'original_quantity': sale_item.quantity,
                    'returned_quantity': total_returned,
                    'available_to_return': available_to_return,
                    'unit_id': sale_item.unit.id,
                    'unit_name': sale_item.unit.name,
                    'unit_price': sale_item.unit_price,
                    'line_total': sale_item.line_total,
                })
        
        return returnable_items
