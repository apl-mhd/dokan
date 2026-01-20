# Sale Return System Documentation

## Overview

The Sale Return system allows customers to return products from previously completed sales. The system handles inventory adjustments, financial refunds, and maintains a complete audit trail of all return transactions.

## Features

- ✅ Create returns for delivered sales only
- ✅ Partial and full returns supported
- ✅ Track return reasons and item conditions
- ✅ Automatic inventory adjustment (restocking)
- ✅ Accounting ledger integration
- ✅ Customer balance updates
- ✅ Multi-tenant support (company-aware)
- ✅ Return number generation
- ✅ Status tracking (Pending, Completed, Cancelled)
- ✅ Refund status tracking
- ✅ Validation to prevent over-returning

## Database Models

### SaleReturn

Main model for tracking sale return transactions.

**Key Fields:**
- `sale` - Reference to original sale (ForeignKey)
- `customer` - Customer making the return
- `company` - Multi-tenant company
- `warehouse` - Warehouse where items are returned
- `return_number` - Unique return identifier (auto-generated)
- `return_date` - Date of return
- `status` - Pending, Completed, or Cancelled
- `refund_status` - Not Refunded, Partial, or Refunded
- `return_reason` - Why items are being returned
- `sub_total`, `tax`, `discount`, `grand_total` - Financial calculations
- `refunded_amount` - Amount refunded to customer

**Relationships:**
- Many SaleReturnItems belong to one SaleReturn
- Links to original Sale
- Links to Customer, Warehouse, Company

### SaleReturnItem

Individual items being returned in a return transaction.

**Key Fields:**
- `sale_return` - Parent return (ForeignKey)
- `sale_item` - Reference to original sale item
- `product` - Product being returned
- `returned_quantity` - Quantity being returned
- `unit` - Unit of measurement
- `unit_price` - Original sale price
- `line_total` - Total for this line item
- `condition` - Condition of returned item (good, damaged, defective, expired, wrong_item)
- `condition_notes` - Additional notes about item condition

**Validation:**
- Cannot return more than original quantity
- Tracks already returned quantities across multiple returns
- Validates product matches original sale item

## Status Flow

### Return Status

```
PENDING → COMPLETED
    ↓
CANCELLED
```

- **PENDING**: Return created but not yet processed
  - Can be updated or cancelled
  - No inventory or accounting impact yet
  
- **COMPLETED**: Return processed
  - Inventory updated (items added back to stock)
  - Accounting entries created
  - Customer balance updated
  - Cannot be modified
  
- **CANCELLED**: Return cancelled
  - No inventory or accounting impact
  - Cannot be modified

### Refund Status

- **NOT_REFUNDED**: No refund given yet
- **PARTIAL**: Partial refund given
- **REFUNDED**: Full refund completed

## API Endpoints

### Base URL: `/api/sales/`

### 1. Create Sale Return

**POST** `/api/sales/returns/`

Create a new sale return for a delivered sale.

**Request Body:**
```json
{
  "sale_id": 123,
  "return_date": "2024-01-20",
  "return_reason": "Customer not satisfied with product quality",
  "items": [
    {
      "sale_item_id": 456,
      "returned_quantity": 2,
      "condition": "damaged",
      "condition_notes": "Box was opened and items have scratches"
    }
  ],
  "tax": 0.00,
  "discount": 0.00,
  "refunded_amount": 100.00,
  "notes": "Customer provided receipt"
}
```

**Response (201 Created):**
```json
{
  "message": "Sale return created successfully",
  "data": {
    "id": 789,
    "return_number": "RET-2024-001",
    "sale": 123,
    "sale_invoice_number": "INV-2024-100",
    "customer": 45,
    "customer_name": "John Doe",
    "status": "pending",
    "refund_status": "refunded",
    "grand_total": "100.00",
    "refunded_amount": "100.00",
    ...
  }
}
```

### 2. List Sale Returns

**GET** `/api/sales/returns/`

List all sale returns with optional filters.

**Query Parameters:**
- `search` - Search by return number, sale invoice, customer name
- `status` - Filter by status (pending, completed, cancelled)
- `refund_status` - Filter by refund status
- `sale_id` - Filter by original sale ID
- `page` - Page number for pagination
- `page_size` - Items per page

**Example:**
```
GET /api/sales/returns/?status=pending&page=1&page_size=20
```

**Response (200 OK):**
```json
{
  "message": "Sale returns retrieved successfully",
  "data": [...],
  "count": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

### 3. Get Sale Return Details

**GET** `/api/sales/returns/{id}/`

Retrieve detailed information about a specific return.

**Response (200 OK):**
```json
{
  "message": "Sale return retrieved successfully",
  "data": {
    "id": 789,
    "return_number": "RET-2024-001",
    "sale": 123,
    "items": [
      {
        "id": 1,
        "sale_item_id": 456,
        "product": 78,
        "product_name": "Widget X",
        "returned_quantity": "2.0000",
        "unit": 5,
        "unit_name": "pcs",
        "unit_price": "50.00",
        "line_total": "100.00",
        "condition": "damaged",
        "condition_notes": "Box was opened"
      }
    ],
    ...
  }
}
```

### 4. Update Sale Return

**PUT** `/api/sales/returns/{id}/`

Update a pending sale return. Only allowed for PENDING returns.

**Request Body:** (Same structure as create)

**Response (200 OK):**
```json
{
  "message": "Sale return updated successfully",
  "data": {...}
}
```

### 5. Complete Sale Return

**POST** `/api/sales/returns/{id}/complete/`

Complete a sale return. This will:
- Update inventory (add items back to stock)
- Create accounting ledger entries
- Update customer balance
- Set status to COMPLETED

**Response (200 OK):**
```json
{
  "message": "Sale return completed successfully",
  "data": {...}
}
```

### 6. Cancel Sale Return

**POST** `/api/sales/returns/{id}/cancel/`

Cancel a pending sale return.

**Response (200 OK):**
```json
{
  "message": "Sale return cancelled successfully",
  "data": {...}
}
```

### 7. Delete Sale Return

**DELETE** `/api/sales/returns/{id}/`

Delete a pending sale return. Only PENDING returns can be deleted.

**Response (204 No Content)**

### 8. Get Returnable Items

**GET** `/api/sales/{sale_id}/returnable-items/`

Get list of items from a sale that can still be returned.

**Response (200 OK):**
```json
{
  "message": "Returnable items retrieved successfully",
  "data": [
    {
      "sale_item_id": 456,
      "product_id": 78,
      "product_name": "Widget X",
      "original_quantity": "10.0000",
      "returned_quantity": "2.0000",
      "available_to_return": "8.0000",
      "unit_id": 5,
      "unit_name": "pcs",
      "unit_price": "50.00",
      "line_total": "500.00"
    }
  ]
}
```

## Business Logic

### Return Creation Workflow

1. **Validation**
   - Verify sale exists and belongs to company
   - Verify sale status is "delivered"
   - Validate return quantities don't exceed available quantities

2. **Return Creation**
   - Generate unique return number
   - Create SaleReturn record with status=PENDING
   - Create SaleReturnItem records for each item
   - Calculate totals (sub_total, tax, discount, grand_total)
   - Calculate refund status based on refunded_amount

3. **Completion Workflow** (when status changes to COMPLETED)
   - **Inventory Update:**
     - Add returned items back to warehouse stock
     - Create stock transactions with type=SALE_RETURN
     - Only items in "good" or "wrong_item" condition are restocked
     - Damaged/defective items are tracked but not restocked
   
   - **Accounting Entries:**
     - Create ledger entry (Credit: Customer Receivable)
     - If refund given, create refund payment entry
     - Update customer balance
   
   - **Status Update:**
     - Set status to COMPLETED
     - Set completed_at timestamp
     - Lock the return from further modifications

### Inventory Management

The system handles inventory differently based on item condition:

**Restocked Conditions:**
- `good` - Item in good condition, can be resold
- `wrong_item` - Wrong item sent, can be resold

**Not Restocked:**
- `damaged` - Item damaged, cannot be resold
- `defective` - Item defective, needs repair/disposal
- `expired` - Item expired, cannot be resold

All return transactions are recorded in stock history regardless of restocking status for complete audit trail.

### Accounting Integration

When a return is completed:

1. **Sale Return Ledger Entry:**
   - Type: SALE_RETURN
   - Credit: Customer Receivable (reduces debt)
   - Amount: grand_total

2. **Refund Payment Entry (if refunded_amount > 0):**
   - Type: PAYMENT_MADE
   - Description: Refund for return
   - Amount: refunded_amount

3. **Customer Balance Update:**
   - Recalculated based on all ledger entries
   - Balance = Debits - Credits

## Validation Rules

### Return Quantity Validation

```python
# For each sale item being returned:
total_returned = sum of all previous returns for this sale_item
available = original_quantity - total_returned
if requested_quantity > available:
    raise ValidationError
```

### Sale Status Validation

Only sales with status="delivered" can have returns created.

### Return Status Transitions

```
PENDING → COMPLETED (allowed)
PENDING → CANCELLED (allowed)
COMPLETED → * (not allowed)
CANCELLED → * (not allowed)
```

## Error Handling

Common error responses:

**400 Bad Request:**
```json
{
  "error": "Validation error",
  "details": "Cannot return more than original quantity..."
}
```

**403 Forbidden:**
```json
{
  "error": "Company context missing. Please ensure CompanyMiddleware is enabled."
}
```

**404 Not Found:**
```json
{
  "error": "Sale not found"
}
```

## Usage Examples

### Example 1: Simple Return

Customer returns 2 items from an order:

```bash
# 1. Check what can be returned
GET /api/sales/123/returnable-items/

# 2. Create return
POST /api/sales/returns/
{
  "sale_id": 123,
  "return_reason": "Changed mind",
  "items": [
    {
      "sale_item_id": 456,
      "returned_quantity": 2,
      "condition": "good"
    }
  ],
  "refunded_amount": 100.00
}

# 3. Complete the return
POST /api/sales/returns/789/complete/
```

### Example 2: Partial Return with Damaged Items

Customer returns some items, some are damaged:

```bash
POST /api/sales/returns/
{
  "sale_id": 123,
  "return_reason": "Some items damaged in transit",
  "items": [
    {
      "sale_item_id": 456,
      "returned_quantity": 3,
      "condition": "good",
      "condition_notes": "Perfect condition"
    },
    {
      "sale_item_id": 457,
      "returned_quantity": 2,
      "condition": "damaged",
      "condition_notes": "Box crushed, product broken"
    }
  ],
  "refunded_amount": 250.00,
  "notes": "Partial refund given, damaged items not restocked"
}
```

### Example 3: Query Returns by Status

```bash
# Get all pending returns
GET /api/sales/returns/?status=pending

# Get completed returns for a specific sale
GET /api/sales/returns/?sale_id=123&status=completed

# Search returns
GET /api/sales/returns/?search=RET-2024-001
```

## Multi-Tenant Support

All operations are company-aware:
- Returns automatically filtered by request.company
- Cross-company access prevented
- All related objects (sale, customer, warehouse) validated to belong to same company

## Testing Checklist

- [ ] Create return for delivered sale
- [ ] Create return for non-delivered sale (should fail)
- [ ] Return more than original quantity (should fail)
- [ ] Return same item twice (track cumulative returns)
- [ ] Complete return and verify inventory updated
- [ ] Complete return and verify ledger entries created
- [ ] Update pending return
- [ ] Update completed return (should fail)
- [ ] Cancel pending return
- [ ] Delete pending return
- [ ] Delete completed return (should fail)
- [ ] Test with different item conditions
- [ ] Test multi-tenant isolation
- [ ] Test pagination and filters

## Migration Commands

After adding the models, create and run migrations:

```bash
python manage.py makemigrations sale
python manage.py migrate sale
```

## Future Enhancements

Potential improvements:
1. Return approval workflow
2. Restocking fee calculation
3. Return period validation (e.g., only allow returns within 30 days)
4. Email notifications for returns
5. Return statistics and analytics
6. Integration with shipping/logistics for return shipping
7. Photo upload for damaged items
8. Return to different warehouse
9. Exchange support (not just returns)
10. Bulk return processing

## Support

For issues or questions about the sale return system:
1. Check this documentation
2. Review the service layer code in `sale/services/sale_return_service.py`
3. Check model definitions in `sale/models.py`
4. Review API views in `sale/views.py`
