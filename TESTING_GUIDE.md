# Multi-Tenant Purchase Flow - Test Examples

## Manual Testing with cURL

### Setup: Get JWT Tokens

```bash
# Get token for Company A user
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "company_a_user",
    "password": "password123"
  }'

# Save the token
export TOKEN_A="<access_token_from_response>"

# Get token for Company B user
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "company_b_user",
    "password": "password123"
  }'

# Save the token
export TOKEN_B="<access_token_from_response>"
```

---

## Test 1: Create Purchase as Company A

```bash
curl -X POST http://localhost:8000/api/purchases/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier": 1,
    "warehouse": 1,
    "status": "pending",
    "invoice_date": "2026-01-03",
    "notes": "Test purchase for Company A",
    "items": [
      {
        "product": 1,
        "quantity": "10.00",
        "unit": 1,
        "unit_price": "150.00"
      }
    ]
  }'

# Expected: 201 Created
# Response includes purchase with company automatically set
```

---

## Test 2: List Purchases as Company A

```bash
curl -X GET http://localhost:8000/api/purchases/ \
  -H "Authorization: Bearer $TOKEN_A"

# Expected: 200 OK
# Should see only Company A's purchases
```

---

## Test 3: Try to Access Company A's Purchase as Company B

```bash
# Get purchase ID from Test 1, let's say it's 1
curl -X GET http://localhost:8000/api/purchases/1/ \
  -H "Authorization: Bearer $TOKEN_B"

# Expected: 404 Not Found
# Company B cannot see Company A's purchase
```

---

## Test 4: List Purchases as Company B

```bash
curl -X GET http://localhost:8000/api/purchases/ \
  -H "Authorization: Bearer $TOKEN_B"

# Expected: 200 OK
# Should see only Company B's purchases (empty if none created)
```

---

## Test 5: Try to Create Purchase with Company B's Supplier as Company A

```bash
# First, create a supplier for Company B (supplier_id = 2)
# Then try to use it as Company A user

curl -X POST http://localhost:8000/api/purchases/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier": 2,
    "warehouse": 1,
    "items": [
      {
        "product": 1,
        "quantity": "10.00",
        "unit": 1,
        "unit_price": "150.00"
      }
    ]
  }'

# Expected: 400 Bad Request
# Error: "Supplier does not belong to your company."
```

---

## Test 6: Update Purchase as Company A

```bash
curl -X PUT http://localhost:8000/api/purchases/1/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "notes": "Updated by Company A",
    "items": [
      {
        "product": 1,
        "quantity": "15.00",
        "unit": 1,
        "unit_price": "150.00"
      }
    ]
  }'

# Expected: 200 OK
# Purchase updated, stock adjusted
```

---

## Test 7: Try to Update Company A's Purchase as Company B

```bash
curl -X PUT http://localhost:8000/api/purchases/1/ \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "cancelled",
    "items": [...]
  }'

# Expected: 404 Not Found
# Company B cannot update Company A's purchase
```

---

## Test 8: Delete Purchase as Company A

```bash
curl -X DELETE http://localhost:8000/api/purchases/1/ \
  -H "Authorization: Bearer $TOKEN_A"

# Expected: 204 No Content
# Purchase deleted successfully
```

---

## Test 9: Try to Delete Company A's Purchase as Company B

```bash
# Create another purchase as Company A (id = 2)
curl -X DELETE http://localhost:8000/api/purchases/2/ \
  -H "Authorization: Bearer $TOKEN_B"

# Expected: 404 Not Found
# Company B cannot delete Company A's purchase
```

---

## Test 10: Create Purchase Without Authentication

```bash
curl -X POST http://localhost:8000/api/purchases/ \
  -H "Content-Type: application/json" \
  -d '{
    "supplier": 1,
    "warehouse": 1,
    "items": [...]
  }'

# Expected: 401 Unauthorized
# Authentication required
```

---

## Python Test Suite Example

Create `purchase/tests/test_multi_tenant.py`:

```python
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from company.models import Company, CompanyUser
from supplier.models import Supplier
from warehouse.models import Warehouse
from product.models import Product, Unit, Category, UnitCategory
from purchase.models import Purchase


class MultiTenantPurchaseTestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create two companies
        self.company_a = Company.objects.create(name="Company A")
        self.company_b = Company.objects.create(name="Company B")
        
        # Create users
        self.user_a = User.objects.create_user('user_a', password='pass')
        self.user_b = User.objects.create_user('user_b', password='pass')
        
        # Associate users with companies
        CompanyUser.objects.create(company=self.company_a, user=self.user_a)
        CompanyUser.objects.create(company=self.company_b, user=self.user_b)
        
        # Create suppliers
        self.supplier_a = Supplier.objects.create(
            name="Supplier A",
            company=self.company_a
        )
        self.supplier_b = Supplier.objects.create(
            name="Supplier B",
            company=self.company_b
        )
        
        # Create warehouses
        self.warehouse_a = Warehouse.objects.create(
            name="Warehouse A",
            company=self.company_a,
            location="Location A"
        )
        self.warehouse_b = Warehouse.objects.create(
            name="Warehouse B",
            company=self.company_b,
            location="Location B"
        )
        
        # Create product, unit, category
        category = Category.objects.create(name="Test Category")
        unit_category = UnitCategory.objects.create(name="Weight")
        unit = Unit.objects.create(
            name="KG",
            unit_category=unit_category,
            is_base_unit=True
        )
        self.product = Product.objects.create(
            name="Test Product",
            category=category,
            base_unit=unit
        )
        self.unit = unit
        
        # Create API clients
        self.client_a = APIClient()
        self.client_b = APIClient()
        
        # Get tokens
        token_a = RefreshToken.for_user(self.user_a)
        token_b = RefreshToken.for_user(self.user_b)
        
        self.client_a.credentials(HTTP_AUTHORIZATION=f'Bearer {token_a.access_token}')
        self.client_b.credentials(HTTP_AUTHORIZATION=f'Bearer {token_b.access_token}')
    
    def test_create_purchase_company_a(self):
        """Test creating a purchase as Company A"""
        data = {
            "supplier": self.supplier_a.id,
            "warehouse": self.warehouse_a.id,
            "status": "pending",
            "items": [
                {
                    "product": self.product.id,
                    "quantity": "10.00",
                    "unit": self.unit.id,
                    "unit_price": "150.00"
                }
            ]
        }
        
        response = self.client_a.post('/api/purchases/', data, format='json')
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data']['company'], self.company_a.id)
    
    def test_list_purchases_company_isolation(self):
        """Test that companies can only see their own purchases"""
        # Create purchase for Company A
        purchase_a = Purchase.objects.create(
            invoice_number="INV-A-001",
            company=self.company_a,
            supplier=self.supplier_a,
            warehouse=self.warehouse_a,
            created_by=self.user_a
        )
        
        # Create purchase for Company B
        purchase_b = Purchase.objects.create(
            invoice_number="INV-B-001",
            company=self.company_b,
            supplier=self.supplier_b,
            warehouse=self.warehouse_b,
            created_by=self.user_b
        )
        
        # Company A should only see their purchase
        response_a = self.client_a.get('/api/purchases/')
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(len(response_a.data['data']), 1)
        self.assertEqual(response_a.data['data'][0]['id'], purchase_a.id)
        
        # Company B should only see their purchase
        response_b = self.client_b.get('/api/purchases/')
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(len(response_b.data['data']), 1)
        self.assertEqual(response_b.data['data'][0]['id'], purchase_b.id)
    
    def test_cannot_access_other_company_purchase(self):
        """Test that Company B cannot access Company A's purchase"""
        purchase_a = Purchase.objects.create(
            invoice_number="INV-A-001",
            company=self.company_a,
            supplier=self.supplier_a,
            warehouse=self.warehouse_a,
            created_by=self.user_a
        )
        
        # Company B tries to access Company A's purchase
        response = self.client_b.get(f'/api/purchases/{purchase_a.id}/')
        self.assertEqual(response.status_code, 404)
    
    def test_cannot_use_other_company_supplier(self):
        """Test that Company A cannot use Company B's supplier"""
        data = {
            "supplier": self.supplier_b.id,  # Company B's supplier
            "warehouse": self.warehouse_a.id,
            "items": [
                {
                    "product": self.product.id,
                    "quantity": "10.00",
                    "unit": self.unit.id,
                    "unit_price": "150.00"
                }
            ]
        }
        
        response = self.client_a.post('/api/purchases/', data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Supplier', str(response.data))
    
    def test_cannot_update_other_company_purchase(self):
        """Test that Company B cannot update Company A's purchase"""
        purchase_a = Purchase.objects.create(
            invoice_number="INV-A-001",
            company=self.company_a,
            supplier=self.supplier_a,
            warehouse=self.warehouse_a,
            created_by=self.user_a
        )
        
        data = {
            "status": "cancelled",
            "items": []
        }
        
        response = self.client_b.put(
            f'/api/purchases/{purchase_a.id}/',
            data,
            format='json'
        )
        self.assertEqual(response.status_code, 404)
    
    def test_cannot_delete_other_company_purchase(self):
        """Test that Company B cannot delete Company A's purchase"""
        purchase_a = Purchase.objects.create(
            invoice_number="INV-A-001",
            company=self.company_a,
            supplier=self.supplier_a,
            warehouse=self.warehouse_a,
            created_by=self.user_a
        )
        
        response = self.client_b.delete(f'/api/purchases/{purchase_a.id}/')
        self.assertEqual(response.status_code, 404)
```

---

## Running Tests

```bash
# Run all tests
python manage.py test

# Run only purchase tests
python manage.py test purchase.tests

# Run specific test case
python manage.py test purchase.tests.test_multi_tenant.MultiTenantPurchaseTestCase

# Run with verbose output
python manage.py test --verbosity=2

# Run with coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report
```

---

## Expected Results

All tests should pass with output like:

```
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
........
----------------------------------------------------------------------
Ran 8 tests in 1.234s

OK
Destroying test database for alias 'default'...
```

---

## Common Test Issues

### Issue: "Company context missing"
**Cause:** CompanyMiddleware not working in tests
**Solution:** Ensure CompanyUser relationship exists in setUp()

### Issue: Tests fail with IntegrityError
**Cause:** Missing required fields in test data
**Solution:** Ensure all ForeignKey relationships are set up in setUp()

### Issue: 404 errors in tests
**Cause:** URL patterns not matching
**Solution:** Check URL configuration in `purchase/urls.py`

---

## Manual Database Verification

```sql
-- Check that purchases are company-isolated
SELECT p.id, p.invoice_number, p.company_id, c.name as company_name
FROM purchase_purchase p
JOIN company_company c ON p.company_id = c.id;

-- Check that purchase items match purchase company
SELECT pi.id, pi.purchase_id, pi.company_id, p.company_id as purchase_company
FROM purchase_purchaseitem pi
JOIN purchase_purchase p ON pi.purchase_id = p.id
WHERE pi.company_id != p.company_id;
-- Should return 0 rows

-- Check stock company isolation
SELECT s.id, s.product_id, s.warehouse_id, s.company_id, s.quantity
FROM inventory_stock s
ORDER BY s.company_id;
```

---

## Success Criteria

✅ All automated tests pass
✅ Manual cURL tests demonstrate data isolation
✅ No cross-company data access possible
✅ Company is automatically set on all records
✅ Database queries show proper company filtering
✅ System check returns no errors
✅ No linter errors

---

Your multi-tenant SaaS implementation is **production-ready** when all these tests pass!

