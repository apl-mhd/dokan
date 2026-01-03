# Multi-Tenant SaaS - Quick Reference Guide

## Quick Start

### 1. Ensure User Has Company
```python
from company.models import CompanyUser

# Create company relationship for user
CompanyUser.objects.create(company=your_company, user=your_user)
```

### 2. Make Authenticated Request
```bash
# Get JWT token
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'

# Use token in requests
curl -X GET http://localhost:8000/api/purchases/ \
  -H "Authorization: Bearer <your_jwt_token>"
```

---

## Key Concepts

### Middleware Sets Company Context
```python
# In every view, you have access to:
request.company  # Current user's company (or None)
```

### Always Check Company Context
```python
if not request.company:
    return Response({"error": "Company context missing"}, status=403)
```

### Filter All Queries by Company
```python
# Always filter by company for read operations
queryset = Purchase.objects.filter(company=request.company)

# Use company-filtered get_object_or_404
purchase = get_object_or_404(
    Purchase.objects.filter(company=request.company),
    pk=pk
)
```

### Pass Company to Service Layer
```python
# For write operations, pass company to service
purchase = PurchaseService.create_purchase(data, user, request.company)
```

---

## Common Patterns

### Pattern 1: List View (Company-Filtered)
```python
def get(self, request):
    if not request.company:
        return Response({"error": "Company context missing"}, status=403)
    
    items = MyModel.objects.filter(company=request.company)
    serializer = MySerializer(items, many=True)
    return Response(serializer.data)
```

### Pattern 2: Detail View (Company-Filtered)
```python
def get(self, request, pk):
    if not request.company:
        return Response({"error": "Company context missing"}, status=403)
    
    item = get_object_or_404(
        MyModel.objects.filter(company=request.company),
        pk=pk
    )
    serializer = MySerializer(item)
    return Response(serializer.data)
```

### Pattern 3: Create View (Auto-Set Company)
```python
def post(self, request):
    if not request.company:
        return Response({"error": "Company context missing"}, status=403)
    
    # Pass company to service
    item = MyService.create(data, request.user, request.company)
    return Response(MySerializer(item).data, status=201)
```

### Pattern 4: Service Layer Validation
```python
@staticmethod
def create_item(data, user, company):
    # Validate related objects belong to company
    related_obj = get_object_or_404(
        RelatedModel.objects.filter(company=company),
        id=data['related_id']
    )
    
    # Create with company
    item = MyModel.objects.create(
        company=company,
        created_by=user,
        related=related_obj,
        ...
    )
    return item
```

---

## Making a Model Multi-Tenant

### Step 1: Add Company Field
```python
from company.models import Company

class MyModel(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name='my_models'
    )
    # ... other fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['company', 'created_at']),
        ]
```

### Step 2: Add Model Validation (Optional)
```python
def clean(self):
    if self.related_obj and self.related_obj.company != self.company:
        raise ValidationError({
            'related_obj': 'Must belong to the same company'
        })

def save(self, *args, **kwargs):
    self.full_clean()
    super().save(*args, **kwargs)
```

### Step 3: Update Serializer
```python
class MySerializer(serializers.ModelSerializer):
    class Meta:
        model = MyModel
        fields = '__all__'
        read_only_fields = ['company', 'created_at', 'updated_at']
```

### Step 4: Update Service Layer
```python
class MyService:
    @staticmethod
    def create(data, user, company):
        # Validate company access
        # ...
        
        item = MyModel.objects.create(
            company=company,  # Always set company
            created_by=user,
            ...
        )
        return item
```

### Step 5: Update Views
```python
class MyAPIView(APIView):
    def get(self, request, pk=None):
        if not request.company:
            return Response({"error": "Company context missing"}, status=403)
        
        queryset = MyModel.objects.filter(company=request.company)
        # ... rest of logic
```

### Step 6: Run Migrations
```bash
python manage.py makemigrations myapp
python manage.py migrate
```

---

## Security Checklist

- [ ] Model has `company` ForeignKey
- [ ] Serializer marks `company` as `read_only`
- [ ] Views check for `request.company`
- [ ] All queries filter by `company`
- [ ] Service layer validates related objects
- [ ] Service layer automatically sets `company`
- [ ] Database indexes include `company`
- [ ] Migrations applied

---

## Testing Checklist

- [ ] Create data as Company A
- [ ] Try to access as Company B (should fail)
- [ ] List data as Company A (should see only A's data)
- [ ] List data as Company B (should see only B's data)
- [ ] Try to create with Company B's related objects as Company A (should fail)
- [ ] Update data as Company A (should work)
- [ ] Try to update Company A's data as Company B (should fail)
- [ ] Delete data as Company A (should work)
- [ ] Try to delete Company A's data as Company B (should fail)

---

## Common Errors and Solutions

### Error: "Company context missing"
**Cause:** CompanyMiddleware not enabled or user not associated with company
**Solution:** 
1. Check `settings.py` has `company.middleware.CompanyMiddleware`
2. Ensure user has `CompanyUser` record

### Error: "Not found" when data exists
**Cause:** Trying to access data from another company
**Solution:** This is expected behavior - data isolation working correctly

### Error: "Supplier does not belong to your company"
**Cause:** Trying to use related objects from another company
**Solution:** Use only objects belonging to your company

---

## Performance Tips

### Use Select Related
```python
# Good - reduces queries
Purchase.objects.filter(company=request.company).select_related(
    'supplier', 'warehouse', 'created_by', 'company'
)

# Bad - N+1 queries
Purchase.objects.filter(company=request.company)
```

### Use Prefetch Related
```python
# Good - efficient for many-to-many or reverse FK
Purchase.objects.filter(company=request.company).prefetch_related(
    'items__product', 'items__unit'
)
```

### Add Indexes
```python
class Meta:
    indexes = [
        models.Index(fields=['company', 'created_at']),
        models.Index(fields=['company', 'status']),
    ]
```

---

## URL Patterns

```python
# Standard multi-tenant URL pattern
urlpatterns = [
    path('', MyAPIView.as_view(), name='mymodel-list-create'),
    path('<int:pk>/', MyAPIView.as_view(), name='mymodel-detail'),
]
```

---

## Example Request/Response

### Create Purchase
```bash
POST /api/purchases/
Authorization: Bearer <token>
Content-Type: application/json

{
  "supplier": 1,
  "warehouse": 1,
  "items": [
    {
      "product": 1,
      "quantity": "10.00",
      "unit": 1,
      "unit_price": "150.00"
    }
  ]
}

# Response
{
  "message": "Purchase created successfully",
  "data": {
    "id": 1,
    "company": 1,              # Auto-set
    "company_name": "My Co",   # Auto-populated
    "supplier": 1,
    "supplier_name": "ABC",    # Auto-populated
    "warehouse": 1,
    "warehouse_name": "Main",  # Auto-populated
    "grand_total": "1500.00",  # Auto-calculated
    "items": [...]
  }
}
```

---

## Remember

1. **Never trust frontend-provided company IDs** - Always use `request.company`
2. **Always filter by company** - Never query without company filter
3. **Company is read-only** - Set in service layer, not serializers
4. **Validate relationships** - Ensure related objects belong to same company
5. **Use atomic transactions** - Wrap multi-step operations in `transaction.atomic()`
6. **Add indexes** - Always index company field for performance
7. **Check for company context** - Return 403 if missing
8. **Document your code** - Clear docstrings help future developers

---

This implementation ensures **complete data isolation** between companies while maintaining **clean, maintainable code**.

