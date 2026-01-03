# Multi-Tenant Purchase API Documentation

## Base URL
All purchase endpoints are available at: `/api/purchases/`

## Authentication
All endpoints require JWT authentication. Include the token in your request headers:
```
Authorization: Bearer <your_jwt_token>
```

## Company Context
All endpoints automatically filter data by the authenticated user's company. The `company` field is:
- ✅ Automatically set from `request.company` (via CompanyMiddleware)
- ✅ Read-only - cannot be modified via API
- ✅ Ensures data isolation between companies

---

## Endpoints

### 1. List All Purchases
**GET** `/api/purchases/`

Returns all purchases belonging to the authenticated user's company.

**Response:**
```json
{
  "message": "Purchases retrieved successfully",
  "data": [
    {
      "id": 1,
      "invoice_number": "uuid-here",
      "company": 1,
      "company_name": "My Company",
      "supplier": 1,
      "supplier_name": "ABC Supplier",
      "warehouse": 1,
      "warehouse_name": "Main Warehouse",
      "status": "pending",
      "grand_total": "1500.00",
      "invoice_date": "2026-01-03",
      "notes": "First purchase",
      "created_by": 1,
      "created_at": "2026-01-03T10:00:00Z",
      "updated_at": "2026-01-03T10:00:00Z",
      "items": [
        {
          "id": 1,
          "product": 1,
          "quantity": "10.00",
          "unit": 1,
          "unit_price": "150.00",
          "line_total": "1500.00",
          "created_at": "2026-01-03T10:00:00Z"
        }
      ]
    }
  ]
}
```

---

### 2. Get Single Purchase
**GET** `/api/purchases/{id}/`

Returns a specific purchase belonging to the authenticated user's company.

**Response:**
```json
{
  "message": "Purchase retrieved successfully",
  "data": {
    "id": 1,
    "invoice_number": "uuid-here",
    "company": 1,
    "company_name": "My Company",
    ...
  }
}
```

**Error Response (if purchase belongs to another company):**
```json
{
  "detail": "Not found."
}
```

---

### 3. Create Purchase
**POST** `/api/purchases/`

Creates a new purchase. The `company` field is automatically set.

**Request Body:**
```json
{
  "supplier": 1,
  "warehouse": 1,
  "status": "pending",
  "invoice_date": "2026-01-03",
  "notes": "New purchase order",
  "items": [
    {
      "product": 1,
      "quantity": "10.00",
      "unit": 1,
      "unit_price": "150.00"
    },
    {
      "product": 2,
      "quantity": "5.00",
      "unit": 2,
      "unit_price": "200.00"
    }
  ]
}
```

**Validation Rules:**
- ✅ `supplier` must belong to your company
- ✅ `warehouse` must belong to your company
- ✅ At least one item is required
- ✅ `quantity` must be greater than 0
- ✅ `unit_price` cannot be negative
- ✅ `company` is automatically set (do not include in request)

**Success Response (201 Created):**
```json
{
  "message": "Purchase created successfully",
  "data": {
    "id": 2,
    "invoice_number": "uuid-here",
    "company": 1,
    "company_name": "My Company",
    "grand_total": "2500.00",
    ...
  }
}
```

**Error Responses:**

**403 Forbidden** - Company context missing:
```json
{
  "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
}
```

**401 Unauthorized** - Not authenticated:
```json
{
  "error": "Authentication required"
}
```

**400 Bad Request** - Validation error:
```json
{
  "error": "Validation error",
  "details": {
    "items": ["At least one item is required."]
  }
}
```

**400 Bad Request** - Cross-company access attempt:
```json
{
  "error": "Validation error",
  "details": "Supplier does not belong to your company."
}
```

---

### 4. Update Purchase
**PUT** `/api/purchases/{id}/`

Updates an existing purchase. Can only update purchases belonging to your company.

**Request Body:**
```json
{
  "status": "completed",
  "notes": "Updated notes",
  "items": [
    {
      "product": 1,
      "quantity": "15.00",
      "unit": 1,
      "unit_price": "150.00"
    }
  ]
}
```

**Notes:**
- ✅ Old stock is automatically reverted
- ✅ New stock is automatically added
- ✅ All transactions are atomic
- ✅ Cannot update purchases from other companies

**Success Response (200 OK):**
```json
{
  "message": "Purchase updated successfully",
  "data": {
    "id": 1,
    "status": "completed",
    "grand_total": "2250.00",
    ...
  }
}
```

---

### 5. Delete Purchase
**DELETE** `/api/purchases/{id}/`

Deletes a purchase. Can only delete purchases belonging to your company.

**Success Response (204 No Content):**
```json
{
  "message": "Purchase deleted successfully"
}
```

**Error Response (403 Forbidden):**
```json
{
  "detail": "Not found."
}
```

---

## Stock Management

### Automatic Stock Updates

When you **create** a purchase:
- ✅ Stock is added to the warehouse
- ✅ `StockTransaction` is created with type `PURCHASE` and direction `IN`
- ✅ Company is automatically set on Stock and StockTransaction

When you **update** a purchase:
- ✅ Old stock is reverted (subtracted)
- ✅ `StockTransaction` is created with type `PURCHASE_RETURN` and direction `OUT`
- ✅ New stock is added
- ✅ `StockTransaction` is created with type `PURCHASE` and direction `IN`
- ✅ All operations are atomic

---

## Security Features

### Data Isolation
1. **Automatic Company Assignment**
   - `Purchase.company` is set from `request.company`
   - `PurchaseItem.company` matches `Purchase.company`
   - Cannot be overridden via API

2. **Company-Filtered Queries**
   - All queries filter by `company`
   - `get_object_or_404` uses company-filtered querysets
   - No way to access another company's data

3. **Cross-Company Prevention**
   - Supplier must belong to your company
   - Warehouse must belong to your company
   - Cannot update/delete purchases from other companies
   - Model-level validation prevents mismatched company data

### Validation Layers
1. **Serializer-level** - Input validation
2. **Service-level** - Business logic validation
3. **Model-level** - Data integrity validation

---

## Common Error Codes

| Status Code | Meaning |
|-------------|---------|
| 200 | Success (GET, PUT) |
| 201 | Created successfully (POST) |
| 204 | Deleted successfully (DELETE) |
| 400 | Validation error or bad request |
| 401 | Authentication required |
| 403 | Forbidden (company context missing or access denied) |
| 404 | Purchase not found (or belongs to another company) |
| 500 | Internal server error |

---

## Example cURL Requests

### Get All Purchases
```bash
curl -X GET http://localhost:8000/api/purchases/ \
  -H "Authorization: Bearer your_jwt_token"
```

### Create Purchase
```bash
curl -X POST http://localhost:8000/api/purchases/ \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier": 1,
    "warehouse": 1,
    "status": "pending",
    "items": [
      {
        "product": 1,
        "quantity": "10.00",
        "unit": 1,
        "unit_price": "150.00"
      }
    ]
  }'
```

### Update Purchase
```bash
curl -X PUT http://localhost:8000/api/purchases/1/ \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "items": [
      {
        "product": 1,
        "quantity": "15.00",
        "unit": 1,
        "unit_price": "150.00"
      }
    ]
  }'
```

### Delete Purchase
```bash
curl -X DELETE http://localhost:8000/api/purchases/1/ \
  -H "Authorization: Bearer your_jwt_token"
```

---

## Testing Multi-Tenant Isolation

To verify multi-tenant isolation:

1. Create two companies (Company A and Company B)
2. Create a user for each company
3. Create purchases for Company A
4. Try to access Company A's purchases as Company B user
5. ✅ Should return 404 or empty list

---

## Database Schema

### Purchase Table
```sql
CREATE TABLE purchase (
  id SERIAL PRIMARY KEY,
  invoice_number VARCHAR(128) UNIQUE,
  company_id INTEGER REFERENCES company(id),
  supplier_id INTEGER REFERENCES supplier(id),
  warehouse_id INTEGER REFERENCES warehouse(id),
  status VARCHAR(20),
  grand_total DECIMAL(10, 2),
  created_by_id INTEGER REFERENCES auth_user(id),
  ...
);

CREATE INDEX idx_purchase_company ON purchase(company_id);
```

### PurchaseItem Table
```sql
CREATE TABLE purchase_item (
  id SERIAL PRIMARY KEY,
  purchase_id INTEGER REFERENCES purchase(id),
  company_id INTEGER REFERENCES company(id),
  product_id INTEGER REFERENCES product(id),
  quantity DECIMAL(10, 2),
  unit_id INTEGER REFERENCES unit(id),
  unit_price DECIMAL(10, 2),
  line_total DECIMAL(10, 2),
  ...
);

CREATE INDEX idx_purchase_item_company ON purchase_item(company_id, purchase_id);
```

### Stock Table
```sql
CREATE TABLE stock (
  id SERIAL PRIMARY KEY,
  product_id INTEGER REFERENCES product(id),
  warehouse_id INTEGER REFERENCES warehouse(id),
  company_id INTEGER REFERENCES company(id),
  quantity DECIMAL(10, 4),
  ...
  UNIQUE(product_id, warehouse_id, company_id)
);

CREATE INDEX idx_stock_company ON stock(company_id, product_id, warehouse_id);
```

---

## Notes

- All timestamps are in UTC
- Decimal fields use `max_digits=10, decimal_places=2` (or 4 for stock)
- Invoice numbers are auto-generated UUIDs
- Stock transactions are logged for audit purposes
- All operations are atomic (using Django's transaction.atomic())

