# Product Module - Migration Instructions

## Changes Made

I've updated the product module to support **multi-tenant architecture** (company-aware), matching your Purchase and Sale modules.

### Modified Files

1. **models.py**
   - Added `company` field to `Product` model
   - Changed `UnitCategory.name` from globally unique to unique per company
   - Changed `Category.name` from globally unique to unique per company
   - Added company validation in `Product.clean()`
   - Added database index on `(company, name)` for Product

2. **views.py**
   - Updated `ProductAPIView` to filter by company
   - Added company context checks in all CRUD operations
   - Updated response format to include `category_name` and `base_unit_name`

3. **services/product_service.py**
   - Added `company` parameter to all methods
   - Updated queries to filter by company when provided
   - Added company validation for category and unit relationships

4. **serializers.py**
   - Added `company_name` field to `ProductSerializer`
   - Made `company` field read-only

## Required Actions

### Step 1: Create Migration

```bash
cd /home/apelmahmud/Documents/dokan/dokan-api
python manage.py makemigrations product
```

This will create a migration for:
- Adding `company` field to Product
- Changing unique constraints on Category and UnitCategory
- Adding database indexes

### Step 2: Handle Existing Data

**IMPORTANT:** If you have existing products in your database, you need to assign them to a company.

The migration will prompt you to provide a default value for the company field on existing products.

**Option A:** Set default company ID
```bash
# During migration, when prompted:
# Select option 1) Provide a one-off default now
# Enter: 1  (or the ID of your main company)
```

**Option B:** Set default in migration file manually

Edit the generated migration file to add:
```python
from django.db import migrations

def set_default_company(apps, schema_editor):
    Product = apps.get_model('product', 'Product')
    Company = apps.get_model('company', 'Company')
    
    # Get the first company or create one
    company = Company.objects.first()
    if company:
        # Assign all existing products to this company
        Product.objects.filter(company__isnull=True).update(company=company)

class Migration(migrations.Migration):
    dependencies = [
        ('product', 'XXXX_previous_migration'),
    ]

    operations = [
        # ... auto-generated operations ...
        migrations.RunPython(set_default_company),
    ]
```

### Step 3: Apply Migration

```bash
python manage.py migrate product
```

### Step 4: Verify

```bash
python manage.py shell
```

```python
from product.models import Product, Category, UnitCategory
from company.models import Company

# Check all products have company
Product.objects.filter(company__isnull=True).count()  # Should be 0

# Verify unique constraints work
company = Company.objects.first()
# This should work (different companies)
company2 = Company.objects.last()
Category.objects.create(name="Electronics", company=company)
Category.objects.create(name="Electronics", company=company2)  # OK

# This should fail (same company)
# Category.objects.create(name="Electronics", company=company)  # Error!
```

## Testing

### Test API Endpoints

```bash
# Get JWT token first
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'

# List products (will filter by user's company)
curl -X GET http://localhost:8000/api/products/list/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Create product (company auto-set from request context)
curl -X POST http://localhost:8000/api/products/list/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Product",
    "category": 1,
    "base_unit": 1,
    "description": "Test description"
  }'
```

## Benefits

✅ **Data Isolation**: Each company only sees their own products  
✅ **Consistency**: Matches your Purchase and Sale module architecture  
✅ **Security**: Prevents cross-company data access  
✅ **Scalability**: Ready for multi-tenant deployment  

## Frontend Compatibility

✅ The frontend code I created already supports this structure  
✅ No frontend changes needed - it expects `company_name` in responses  
✅ Company is automatically handled by CompanyMiddleware  

## Next Steps

After running the migration:

1. ✅ Product module will be fully multi-tenant
2. Test with your frontend
3. Consider creating similar updates for Customer and Warehouse modules
4. Add inventory/stock endpoints as documented in `CREATE_BACKEND_APIS.md`

## Rollback (if needed)

If you need to rollback:

```bash
# Check current migrations
python manage.py showmigrations product

# Rollback to previous migration
python manage.py migrate product XXXX_previous_migration_name
```

## Questions?

- Check if CompanyMiddleware is enabled in your settings
- Verify JWT tokens contain company context
- Test with multiple companies to ensure isolation

---

**Status**: Ready to migrate! Run `python manage.py makemigrations product` to begin.

