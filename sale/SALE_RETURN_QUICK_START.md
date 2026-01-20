# Sale Return Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Step 1: Apply Migrations ✅ (DONE)

The migrations have been created. Now apply them:

```bash
cd /home/apelmahmud/Documents/dokan/dokan-api
python manage.py migrate sale
```

**Expected Output:**
```
Running migrations:
  Applying sale.0002_salereturn_salereturnitem_and_more... OK
```

### Step 2: Verify Installation

Check that everything is working:

```bash
python manage.py check sale
```

**Expected Output:**
```
System check identified no issues (0 silenced).
```

### Step 3: Access Admin Interface (Optional)

1. Start your development server:
   ```bash
   python manage.py runserver
   ```

2. Go to: `http://localhost:8000/admin/`

3. You should see:
   - **Sale Returns** in the admin sidebar
   - Ability to view/create/edit returns

### Step 4: Test the API

#### 4.1 First, create a test sale with status "delivered"

```bash
curl -X POST 'http://localhost:8000/api/sales/' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1' \
  -d '{
    "customer": 1,
    "warehouse": 1,
    "status": "delivered",
    "items": [
      {
        "product": 1,
        "quantity": 10,
        "unit": 1,
        "unit_price": 50.00
      }
    ]
  }'
```

#### 4.2 Check what can be returned

```bash
curl -X GET 'http://localhost:8000/api/sales/SALE_ID/returnable-items/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1'
```

Replace `SALE_ID` with the ID from step 4.1.

#### 4.3 Create a return

```bash
curl -X POST 'http://localhost:8000/api/sales/returns/' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1' \
  -d '{
    "sale_id": SALE_ID,
    "return_reason": "Testing sale return",
    "items": [
      {
        "sale_item_id": SALE_ITEM_ID,
        "returned_quantity": 2,
        "condition": "good"
      }
    ],
    "refunded_amount": 100.00
  }'
```

Replace `SALE_ID` and `SALE_ITEM_ID` with actual IDs.

#### 4.4 Complete the return

```bash
curl -X POST 'http://localhost:8000/api/sales/returns/RETURN_ID/complete/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1'
```

Replace `RETURN_ID` with the ID from step 4.3.

### Step 5: Verify Results

After completing the return, verify:

1. **Inventory Updated**
   - Check warehouse stock increased by returned quantity
   - View stock transactions for SALE_RETURN entries

2. **Accounting Entries Created**
   - Check customer ledger for return entry
   - Verify customer balance updated

3. **Return Locked**
   - Try to update/delete completed return (should fail)

## 📚 Available Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sales/returns/` | GET | List returns |
| `/api/sales/returns/` | POST | Create return |
| `/api/sales/returns/{id}/` | GET | Get return details |
| `/api/sales/returns/{id}/` | PUT | Update return |
| `/api/sales/returns/{id}/` | DELETE | Delete return |
| `/api/sales/returns/{id}/complete/` | POST | Complete return |
| `/api/sales/returns/{id}/cancel/` | POST | Cancel return |
| `/api/sales/{id}/returnable-items/` | GET | Get returnable items |

## 📖 Documentation Files

- **SALE_RETURN_DOCUMENTATION.md** - Complete feature documentation
- **SALE_RETURN_IMPLEMENTATION_SUMMARY.md** - Technical implementation details
- **SALE_RETURN_API_TESTING.md** - API testing examples
- **SALE_RETURN_QUICK_START.md** - This file

## 🔍 Key Files Created/Modified

### New Files
- `sale/services/sale_return_service.py` - Business logic
- `sale/SALE_RETURN_*.md` - Documentation

### Modified Files
- `sale/models.py` - Added SaleReturn and SaleReturnItem models
- `sale/serializers.py` - Added return serializers
- `sale/views.py` - Added return API views
- `sale/urls.py` - Added return URL routes
- `sale/admin.py` - Added return admin interface
- `accounting/services/ledger_service.py` - Added return ledger method

## ✅ Testing Checklist

Quick tests to run:

- [ ] Migrations applied successfully
- [ ] Can view returns in admin
- [ ] Can create return for delivered sale
- [ ] Cannot create return for pending sale
- [ ] Can view returnable items
- [ ] Can complete return
- [ ] Inventory updated after completion
- [ ] Cannot modify completed return
- [ ] Can cancel pending return
- [ ] Can filter returns by status

## 🎯 Common Use Cases

### Use Case 1: Customer Returns Defective Product
```json
POST /api/sales/returns/
{
  "sale_id": 123,
  "return_reason": "Product defective",
  "items": [{
    "sale_item_id": 456,
    "returned_quantity": 1,
    "condition": "defective",
    "condition_notes": "Does not power on"
  }],
  "refunded_amount": 50.00
}
```

### Use Case 2: Customer Returns Unused Items
```json
POST /api/sales/returns/
{
  "sale_id": 123,
  "return_reason": "Changed mind",
  "items": [{
    "sale_item_id": 456,
    "returned_quantity": 5,
    "condition": "good"
  }],
  "refunded_amount": 250.00
}
```

### Use Case 3: Partial Return
```json
POST /api/sales/returns/
{
  "sale_id": 123,
  "return_reason": "Ordered too many",
  "items": [{
    "sale_item_id": 456,
    "returned_quantity": 3,
    "condition": "good"
  }],
  "refunded_amount": 150.00
}
```

## 🔒 Security Features

✅ Multi-tenant isolation (company-based filtering)
✅ Authentication required
✅ Authorization checks
✅ Input validation
✅ Transaction safety (atomic operations)

## 💡 Tips

1. **Always complete returns** - Don't leave them in pending status
2. **Use condition field** - Helps track why items were returned
3. **Check returnable items first** - Before creating a return
4. **Document return reasons** - Useful for analytics later
5. **Monitor inventory** - After completing returns

## ❓ Troubleshooting

### Problem: "Sale does not belong to your company"
**Solution:** Ensure you're using the correct X-Company-ID header

### Problem: "Cannot create return for sale with status 'pending'"
**Solution:** Only delivered sales can have returns. Update sale status to delivered first.

### Problem: "Cannot return more than original quantity"
**Solution:** Check returnable-items endpoint to see how much is available

### Problem: Migrations not applying
**Solution:** 
```bash
python manage.py makemigrations sale
python manage.py migrate sale
```

### Problem: Import errors
**Solution:** Restart Django server:
```bash
# Press Ctrl+C to stop
python manage.py runserver
```

## 🎉 Next Steps

1. ✅ Apply migrations
2. ✅ Test basic functionality
3. 📝 Integrate with frontend (if applicable)
4. 🔐 Set up permissions/roles
5. 📊 Create reports/analytics
6. 🚀 Deploy to production

## 📞 Support

If you need help:
1. Check the documentation files
2. Review code comments in service layer
3. Check Django logs for errors
4. Verify middleware is enabled

## 🎊 Success!

If you've completed all the steps above, your sale return system is ready to use!

**Happy coding! 🚀**
