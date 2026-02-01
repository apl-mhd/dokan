from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError
from product.models import Product, Unit, UnitCategory, Category
from rest_framework.exceptions import ValidationError


class ProductService:

    @staticmethod
    def create_product(data, company=None):
        """
        Create a new product.

        Args:
            data: Dictionary containing product data
            company: Company instance (for multi-tenant support)

        Returns:
            Product instance
        """
        category = get_object_or_404(Category, id=data.get('category'))
        
        # Validate category belongs to company if provided
        if company and category.company != company:
            raise ValidationError({
                'category': 'Category does not belong to your company.'
            })
            
        base_unit = None
        if data.get('base_unit'):
            base_unit = get_object_or_404(Unit, id=data.get('base_unit'))
            # Validate base_unit is actually a base unit
            if not base_unit.is_base_unit:
                raise ValidationError({
                    'base_unit': 'Product base_unit must be a base unit (is_base_unit=True).'
                })
            # Validate unit belongs to company if provided
            if company and base_unit.company != company:
                raise ValidationError({
                    'base_unit': 'Unit does not belong to your company.'
                })

        try:
            product = Product.objects.create(
                name=data.get('name'),
                description=data.get('description', ''),
                category=category,
                base_unit=base_unit,
                company=company or category.company,  # Use category's company as fallback
                purchase_price=data.get('purchase_price', 0),
                selling_price=data.get('selling_price', 0),
            )
            product.full_clean()  # Run validation
            return product
        except IntegrityError as e:
            raise ValidationError(f"Error creating product: {str(e)}")

    @staticmethod
    def update_product(product_id, data, company=None):
        """
        Update an existing product.

        Args:
            product_id: ID of the product to update
            data: Dictionary containing updated product data
            company: Company instance (for multi-tenant support)

        Returns:
            Product instance
        """
        queryset = Product.objects.all()
        if company:
            queryset = queryset.filter(company=company)
        product = get_object_or_404(queryset, id=product_id)

        try:
            with transaction.atomic():
                if 'category' in data:
                    category = get_object_or_404(
                        Category, id=data.get('category'))
                    # Validate category belongs to company
                    if company and category.company != company:
                        raise ValidationError({
                            'category': 'Category does not belong to your company.'
                        })
                    product.category = category

                if 'base_unit' in data:
                    # Allow base_unit change even if product has purchase/sale history (no restriction).
                    base_unit_id = data.get('base_unit')
                    if base_unit_id:
                        base_unit = get_object_or_404(Unit, id=base_unit_id)
                        if not base_unit.is_base_unit:
                            raise ValidationError({
                                'base_unit': 'Product base_unit must be a base unit (is_base_unit=True).'
                            })
                        # Validate unit belongs to company
                        if company and base_unit.company != company:
                            raise ValidationError({
                                'base_unit': 'Unit does not belong to your company.'
                            })
                        product.base_unit = base_unit
                    else:
                        product.base_unit = None

                if 'name' in data:
                    product.name = data.get('name')
                if 'description' in data:
                    product.description = data.get('description', '')

                if 'purchase_price' in data:
                    product.purchase_price = data.get('purchase_price')
                if 'selling_price' in data:
                    product.selling_price = data.get('selling_price')

                product.full_clean()  # Run validation
                product.save()
                return product

        except IntegrityError as e:
            raise ValidationError(f"Error updating product: {str(e)}")

    @staticmethod
    def delete_product(product_id, company=None):
        """
        Delete a product.

        Args:
            product_id: ID of the product to delete
            company: Company instance (for multi-tenant support)

        Returns:
            True if successful
        """
        queryset = Product.objects.all()
        if company:
            queryset = queryset.filter(company=company)
        product = get_object_or_404(queryset, id=product_id)

        try:
            product.delete()
            return True
        except Exception as e:
            raise ValidationError(f"Error deleting product: {str(e)}")

    @staticmethod
    def get_product(product_id, company=None):
        """
        Get a single product by ID.

        Args:
            product_id: ID of the product
            company: Company instance (for multi-tenant support)

        Returns:
            Product instance
        """
        queryset = Product.objects.select_related(
            'category', 'base_unit__unit_category', 'company'
        ).prefetch_related('stocks')
        
        if company:
            queryset = queryset.filter(company=company)
            
        return get_object_or_404(queryset, id=product_id)

    @staticmethod
    def get_all_products(company=None):
        """
        Get all products with related data.

        Args:
            company: Company instance (for multi-tenant support)

        Returns:
            QuerySet of Product instances
        """
        queryset = Product.objects.select_related(
            'category', 'base_unit__unit_category', 'company'
        ).prefetch_related('stocks')
        
        if company:
            queryset = queryset.filter(company=company)
            
        return queryset.all()

    @staticmethod
    def get_product_units(product_id):
        """
        Get all units available for a product based on its base unit category.

        Args:
            product_id: ID of the product

        Returns:
            List of Unit instances
        """
        product = get_object_or_404(Product, id=product_id)

        if not product.base_unit or not product.base_unit.unit_category:
            return Unit.objects.none()

        return Unit.objects.filter(
            unit_category=product.base_unit.unit_category
        ).order_by('is_base_unit', 'name')

    @staticmethod
    def check_stock_availability(product_id, unit_id, quantity, warehouse_id):
        """
        Check if required stock is available for a product in a specific unit.

        Args:
            product_id: ID of the product
            unit_id: ID of the unit
            quantity: Required quantity in the specified unit
            warehouse_id: ID of the warehouse

        Returns:
            Dictionary with availability information
        """
        from inventory.models import Stock

        product = get_object_or_404(Product, id=product_id)
        unit = get_object_or_404(Unit, id=unit_id)

        # Convert quantity to base unit
        required_base_quantity = unit.convert_to_base_unit(
            Decimal(str(quantity)))

        # Get stock in base unit
        stock = Stock.objects.filter(
            product_id=product_id,
            warehouse_id=warehouse_id
        ).first()

        available_stock = stock.quantity if stock else Decimal('0.00')
        is_available = available_stock >= required_base_quantity

        # Get base unit name
        base_unit_name = product.base_unit.name if product.base_unit else "N/A"

        return {
            'is_available': is_available,
            'required_quantity': str(required_base_quantity),
            'available_stock': str(available_stock),
            'base_unit': base_unit_name,
            'required_quantity_in_unit': str(quantity),
            'unit_name': unit.name
        }


class UnitService:

    @staticmethod
    def create_unit(data):
        """
        Create a new unit.

        Args:
            data: Dictionary containing unit data

        Returns:
            Unit instance
        """
        unit_category = None
        if data.get('unit_category'):
            unit_category = get_object_or_404(
                UnitCategory, id=data.get('unit_category'))

        try:
            unit = Unit.objects.create(
                name=data.get('name'),
                conversion_factor=Decimal(
                    str(data.get('conversion_factor', 1.0))),
                is_base_unit=data.get('is_base_unit', False),
                unit_category=unit_category,
            )
            unit.full_clean()  # Run validation
            return unit
        except IntegrityError as e:
            raise ValidationError(f"Error creating unit: {str(e)}")

    @staticmethod
    def update_unit(unit_id, data):
        """
        Update an existing unit.

        Args:
            unit_id: ID of the unit to update
            data: Dictionary containing updated unit data

        Returns:
            Unit instance
        """
        unit = get_object_or_404(Unit, id=unit_id)

        try:
            with transaction.atomic():
                if 'unit_category' in data:
                    unit_category_id = data.get('unit_category')
                    if unit_category_id:
                        unit.unit_category = get_object_or_404(
                            UnitCategory, id=unit_category_id)
                    else:
                        unit.unit_category = None

                if 'name' in data:
                    unit.name = data.get('name')
                if 'conversion_factor' in data:
                    unit.conversion_factor = Decimal(
                        str(data.get('conversion_factor')))
                if 'is_base_unit' in data:
                    unit.is_base_unit = data.get('is_base_unit')

                unit.full_clean()  # Run validation
                unit.save()
                return unit

        except IntegrityError as e:
            raise ValidationError(f"Error updating unit: {str(e)}")

    @staticmethod
    def delete_unit(unit_id):
        """
        Delete a unit.

        Args:
            unit_id: ID of the unit to delete

        Returns:
            True if successful
        """
        unit = get_object_or_404(Unit, id=unit_id)

        try:
            unit.delete()
            return True
        except Exception as e:
            raise ValidationError(f"Error deleting unit: {str(e)}")

    @staticmethod
    def get_unit(unit_id):
        """
        Get a single unit by ID.

        Args:
            unit_id: ID of the unit

        Returns:
            Unit instance
        """
        return get_object_or_404(Unit.objects.select_related('unit_category'), id=unit_id)

    @staticmethod
    def get_all_units(company=None):
        """
        Get all units.

        Args:
            company: Company instance (for multi-tenant support)

        Returns:
            QuerySet of Unit instances
        """
        queryset = Unit.objects.select_related('unit_category', 'company')
        
        if company:
            queryset = queryset.filter(company=company)
            
        return queryset.all()


class UnitCategoryService:

    @staticmethod
    def create_unit_category(data):
        """
        Create a new unit category.

        Args:
            data: Dictionary containing unit category data

        Returns:
            UnitCategory instance
        """
        try:
            unit_category = UnitCategory.objects.create(
                name=data.get('name'),
            )
            unit_category.full_clean()  # Run validation
            return unit_category
        except IntegrityError as e:
            raise ValidationError(f"Error creating unit category: {str(e)}")

    @staticmethod
    def update_unit_category(category_id, data):
        """
        Update an existing unit category.

        Args:
            category_id: ID of the unit category to update
            data: Dictionary containing updated unit category data

        Returns:
            UnitCategory instance
        """
        unit_category = get_object_or_404(UnitCategory, id=category_id)

        try:
            with transaction.atomic():
                if 'name' in data:
                    unit_category.name = data.get('name')

                unit_category.full_clean()  # Run validation
                unit_category.save()
                return unit_category

        except IntegrityError as e:
            raise ValidationError(f"Error updating unit category: {str(e)}")

    @staticmethod
    def delete_unit_category(category_id):
        """
        Delete a unit category.

        Args:
            category_id: ID of the unit category to delete

        Returns:
            True if successful
        """
        unit_category = get_object_or_404(UnitCategory, id=category_id)

        try:
            unit_category.delete()
            return True
        except Exception as e:
            raise ValidationError(f"Error deleting unit category: {str(e)}")

    @staticmethod
    def get_unit_category(category_id):
        """
        Get a single unit category by ID.

        Args:
            category_id: ID of the unit category

        Returns:
            UnitCategory instance
        """
        return get_object_or_404(UnitCategory, id=category_id)

    @staticmethod
    def get_all_unit_categories():
        """
        Get all unit categories.

        Returns:
            QuerySet of UnitCategory instances
        """
        return UnitCategory.objects.all()
