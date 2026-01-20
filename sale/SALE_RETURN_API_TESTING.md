# Sale Return API Testing Guide

Quick reference for testing the Sale Return API endpoints.

## Prerequisites

- Django server running
- Valid authentication token
- Company ID for multi-tenant context
- At least one delivered sale with items

## Base URL

```
http://localhost:8000/api/sales/
```

## Authentication Headers

All requests require:
```http
Authorization: Bearer <your-token>
X-Company-ID: <company-id>
Content-Type: application/json
```

## API Endpoints

### 1. Get Returnable Items

Check what items can be returned from a sale.

```bash
GET /api/sales/{sale_id}/returnable-items/
```

**Example Request:**
```bash
curl -X GET 'http://localhost:8000/api/sales/1/returnable-items/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1'
```

**Example Response:**
```json
{
  "message": "Returnable items retrieved successfully",
  "data": [
    {
      "sale_item_id": 1,
      "product_id": 5,
      "product_name": "Widget A",
      "original_quantity": "10.0000",
      "returned_quantity": "0.0000",
      "available_to_return": "10.0000",
      "unit_id": 1,
      "unit_name": "pcs",
      "unit_price": "50.00",
      "line_total": "500.00"
    }
  ]
}
```

---

### 2. Create Sale Return

Create a new return for delivered sales.

```bash
POST /api/sales/returns/
```

**Example Request:**
```bash
curl -X POST 'http://localhost:8000/api/sales/returns/' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1' \
  -d '{
    "sale_id": 1,
    "return_date": "2024-01-20",
    "return_reason": "Product defective",
    "items": [
      {
        "sale_item_id": 1,
        "returned_quantity": 2,
        "condition": "defective",
        "condition_notes": "Does not turn on"
      }
    ],
    "tax": 0.00,
    "discount": 0.00,
    "refunded_amount": 100.00,
    "notes": "Customer provided receipt"
  }'
```

**Request Body Fields:**
- `sale_id` (required) - ID of the original sale
- `return_date` (optional) - Date of return (defaults to today)
- `return_reason` (required) - Reason for return
- `items` (required) - Array of items being returned
  - `sale_item_id` (required) - ID of the sale item
  - `returned_quantity` (required) - Quantity being returned
  - `condition` (optional) - Item condition: good, damaged, defective, expired, wrong_item
  - `condition_notes` (optional) - Additional notes
- `tax` (optional) - Tax amount
- `discount` (optional) - Discount amount
- `refunded_amount` (optional) - Amount refunded to customer
- `notes` (optional) - Additional notes

**Example Response:**
```json
{
  "message": "Sale return created successfully",
  "data": {
    "id": 1,
    "return_number": "RET-2024-001",
    "sale": 1,
    "sale_invoice_number": "INV-2024-001",
    "customer": 1,
    "customer_name": "John Doe",
    "warehouse": 1,
    "warehouse_name": "Main Warehouse",
    "status": "pending",
    "refund_status": "refunded",
    "return_date": "2024-01-20",
    "return_reason": "Product defective",
    "sub_total": "100.00",
    "tax": "0.00",
    "discount": "0.00",
    "grand_total": "100.00",
    "refunded_amount": "100.00",
    "notes": "Customer provided receipt",
    "items": [
      {
        "id": 1,
        "sale_item_id": 1,
        "product": 5,
        "product_name": "Widget A",
        "returned_quantity": "2.0000",
        "unit": 1,
        "unit_name": "pcs",
        "unit_price": "50.00",
        "line_total": "100.00",
        "condition": "defective",
        "condition_notes": "Does not turn on"
      }
    ],
    "created_at": "2024-01-20T10:30:00Z"
  }
}
```

---

### 3. List Sale Returns

Get list of all returns with optional filtering.

```bash
GET /api/sales/returns/?status=pending&page=1&page_size=20
```

**Query Parameters:**
- `search` - Search by return number, sale invoice, customer name
- `status` - Filter by status: pending, completed, cancelled
- `refund_status` - Filter by refund status: not_refunded, partial, refunded
- `sale_id` - Filter by specific sale
- `page` - Page number for pagination
- `page_size` - Number of items per page

**Example Request:**
```bash
curl -X GET 'http://localhost:8000/api/sales/returns/?status=pending' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1'
```

**Example Response:**
```json
{
  "message": "Sale returns retrieved successfully",
  "data": [
    {
      "id": 1,
      "return_number": "RET-2024-001",
      "status": "pending",
      ...
    }
  ],
  "count": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

### 4. Get Sale Return Details

Retrieve detailed information about a specific return.

```bash
GET /api/sales/returns/{id}/
```

**Example Request:**
```bash
curl -X GET 'http://localhost:8000/api/sales/returns/1/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1'
```

---

### 5. Update Sale Return

Update a pending sale return. Only PENDING returns can be updated.

```bash
PUT /api/sales/returns/{id}/
```

**Example Request:**
```bash
curl -X PUT 'http://localhost:8000/api/sales/returns/1/' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1' \
  -d '{
    "id": 1,
    "return_reason": "Updated reason",
    "items": [
      {
        "sale_item_id": 1,
        "returned_quantity": 3,
        "condition": "damaged"
      }
    ],
    "refunded_amount": 150.00
  }'
```

---

### 6. Complete Sale Return

Complete a return. This will update inventory and create accounting entries.

```bash
POST /api/sales/returns/{id}/complete/
```

**Example Request:**
```bash
curl -X POST 'http://localhost:8000/api/sales/returns/1/complete/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1'
```

**What happens:**
1. Inventory is updated (items added back to stock based on condition)
2. Accounting ledger entries are created
3. Customer balance is updated
4. Status changes to COMPLETED
5. Return is locked from further modifications

**Example Response:**
```json
{
  "message": "Sale return completed successfully",
  "data": {
    "id": 1,
    "status": "completed",
    "completed_at": "2024-01-20T11:00:00Z",
    ...
  }
}
```

---

### 7. Cancel Sale Return

Cancel a pending return. Only PENDING returns can be cancelled.

```bash
POST /api/sales/returns/{id}/cancel/
```

**Example Request:**
```bash
curl -X POST 'http://localhost:8000/api/sales/returns/1/cancel/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1'
```

**Example Response:**
```json
{
  "message": "Sale return cancelled successfully",
  "data": {
    "id": 1,
    "status": "cancelled",
    "cancelled_at": "2024-01-20T11:15:00Z",
    ...
  }
}
```

---

### 8. Delete Sale Return

Delete a pending return. Only PENDING returns can be deleted.

```bash
DELETE /api/sales/returns/{id}/
```

**Example Request:**
```bash
curl -X DELETE 'http://localhost:8000/api/sales/returns/1/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1'
```

**Example Response:**
```
HTTP 204 No Content
```

---

## Testing Workflow

### Complete Test Scenario

```bash
# Step 1: Check what can be returned from a sale
curl -X GET 'http://localhost:8000/api/sales/1/returnable-items/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1'

# Step 2: Create a return
curl -X POST 'http://localhost:8000/api/sales/returns/' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1' \
  -d '{
    "sale_id": 1,
    "return_reason": "Customer not satisfied",
    "items": [
      {
        "sale_item_id": 1,
        "returned_quantity": 2,
        "condition": "good"
      }
    ],
    "refunded_amount": 100.00
  }'

# Step 3: Get the return details (use ID from step 2 response)
curl -X GET 'http://localhost:8000/api/sales/returns/1/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1'

# Step 4: Complete the return
curl -X POST 'http://localhost:8000/api/sales/returns/1/complete/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'X-Company-ID: 1'

# Step 5: Verify inventory was updated
# Check stock in inventory endpoint

# Step 6: Verify accounting entries were created
# Check ledger entries for customer
```

## Error Responses

### 400 Bad Request
```json
{
  "error": "Validation error",
  "details": "Cannot return more than original quantity. Original: 10.0000, Already returned: 2.0000, Attempting to return: 10.0000"
}
```

### 401 Unauthorized
```json
{
  "error": "Authentication required"
}
```

### 403 Forbidden
```json
{
  "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "details": "Error message here"
}
```

## Common Testing Scenarios

### Scenario 1: Full Return
Return all items from a sale:
```json
{
  "sale_id": 1,
  "return_reason": "Order cancelled",
  "items": [
    {
      "sale_item_id": 1,
      "returned_quantity": 10,
      "condition": "good"
    }
  ],
  "refunded_amount": 500.00
}
```

### Scenario 2: Partial Return
Return only some items:
```json
{
  "sale_id": 1,
  "return_reason": "Ordered too many",
  "items": [
    {
      "sale_item_id": 1,
      "returned_quantity": 5,
      "condition": "good"
    }
  ],
  "refunded_amount": 250.00
}
```

### Scenario 3: Damaged Items
Return damaged items (won't be restocked):
```json
{
  "sale_id": 1,
  "return_reason": "Items arrived damaged",
  "items": [
    {
      "sale_item_id": 1,
      "returned_quantity": 3,
      "condition": "damaged",
      "condition_notes": "Box was crushed during shipping"
    }
  ],
  "refunded_amount": 150.00
}
```

### Scenario 4: Multiple Items
Return multiple different items:
```json
{
  "sale_id": 1,
  "return_reason": "Mixed issues",
  "items": [
    {
      "sale_item_id": 1,
      "returned_quantity": 2,
      "condition": "good"
    },
    {
      "sale_item_id": 2,
      "returned_quantity": 1,
      "condition": "defective",
      "condition_notes": "Does not work"
    }
  ],
  "refunded_amount": 175.00
}
```

### Scenario 5: No Refund Yet
Create return but haven't refunded yet:
```json
{
  "sale_id": 1,
  "return_reason": "Pending inspection",
  "items": [
    {
      "sale_item_id": 1,
      "returned_quantity": 2,
      "condition": "good"
    }
  ],
  "refunded_amount": 0.00
}
```

## Validation Testing

### Test: Cannot return non-delivered sale
```bash
# Try to create return for pending sale (should fail)
# Error: "Cannot create return for sale with status 'pending'"
```

### Test: Cannot over-return
```bash
# Try to return more than original quantity (should fail)
# Error: "Cannot return 15 units of Product A. Original quantity: 10..."
```

### Test: Cannot modify completed return
```bash
# Try to update a completed return (should fail)
# Error: "Cannot update sale return with status 'completed'"
```

### Test: Multiple returns for same sale
```bash
# Return 2 items first
# Then try to return 10 more (if original was 10, should fail)
# Error: "Available to return: 8"
```

## Tips

1. **Always check returnable items first** - Use the returnable-items endpoint to see what's available
2. **Status matters** - Only pending returns can be modified or deleted
3. **Completion is final** - Once completed, a return cannot be modified
4. **Condition affects inventory** - Only "good" and "wrong_item" conditions get restocked
5. **Test with pagination** - Use page and page_size for large datasets

## Postman Collection

You can import these endpoints into Postman by creating a collection with:
- Base URL variable: `{{base_url}}`
- Token variable: `{{token}}`
- Company ID variable: `{{company_id}}`

Save these as environment variables in Postman for easier testing.
