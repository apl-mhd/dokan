from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Count, Q, F, DecimalField
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from purchase.models import Purchase
from sale.models import Sale
from inventory.models import Stock, StockTransaction
from payment.models import Payment, PaymentType, PaymentStatus


class DashboardStatsAPIView(APIView):
    """
    Provides dashboard statistics for sales and purchases.
    Company-filtered: only shows data belonging to user's company.
    """

    def get(self, request):
        if not hasattr(request, 'company') or not request.company:
            return Response({
                "error": "Company context missing"
            }, status=status.HTTP_403_FORBIDDEN)

        company = request.company
        today = timezone.now().date()
        month_start = today.replace(day=1)

        # Sales Statistics
        sales_today = Sale.objects.filter(
            company=company,
            invoice_date=today
        ).aggregate(
            total=Sum('grand_total'),
            count=Count('id')
        )

        sales_month = Sale.objects.filter(
            company=company,
            invoice_date__gte=month_start
        ).aggregate(
            total=Sum('grand_total'),
            count=Count('id')
        )

        # Calculate customer dues: sum of (grand_total - paid_amount) for all sales
        # This gives the actual outstanding amount customers owe
        # Only count sales where there's an outstanding balance (grand_total > paid_amount)
        customer_dues_result = Sale.objects.filter(
            company=company
        ).annotate(
            outstanding=F('grand_total') - F('paid_amount')
        ).filter(
            outstanding__gt=0
        ).aggregate(
            total_dues=Sum('outstanding', output_field=DecimalField())
        )

        pending_customer_dues = {
            'total': customer_dues_result['total_dues'] or Decimal('0.00')
        }

        # Purchase Statistics
        purchases_today = Purchase.objects.filter(
            company=company,
            invoice_date=today
        ).aggregate(
            total=Sum('grand_total'),
            count=Count('id')
        )

        purchases_month = Purchase.objects.filter(
            company=company,
            invoice_date__gte=month_start
        ).aggregate(
            total=Sum('grand_total'),
            count=Count('id')
        )

        # Calculate supplier dues: sum of (grand_total - paid_amount) for all purchases
        # This gives the actual outstanding amount owed to suppliers
        # Only count purchases where there's an outstanding balance (grand_total > paid_amount)
        supplier_dues_result = Purchase.objects.filter(
            company=company
        ).annotate(
            outstanding=F('grand_total') - F('paid_amount')
        ).filter(
            outstanding__gt=0
        ).aggregate(
            total_dues=Sum('outstanding', output_field=DecimalField())
        )

        supplier_outstanding = {
            'total': supplier_dues_result['total_dues'] or Decimal('0.00')
        }

        # Get period parameter (weekly, monthly, or custom)
        period = request.query_params.get('period', 'weekly')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        product_ids_param = request.query_params.get('product_ids', '')
        product_sales_period = request.query_params.get('product_sales_period', period)
        product_sales_date_from = request.query_params.get('product_sales_date_from')
        product_sales_date_to = request.query_params.get('product_sales_date_to')

        # Parse product IDs for product_sales filter
        product_ids = []
        if product_ids_param:
            try:
                product_ids = [int(x.strip()) for x in product_ids_param.split(',') if x.strip()]
            except (ValueError, TypeError):
                pass

        # Determine date range
        if date_from and date_to and period == 'custom':
            try:
                start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                date_list = []
                current_date = start_date
                while current_date <= end_date:
                    date_list.append(current_date)
                    current_date += timedelta(days=1)
            except ValueError:
                # Invalid date format, fall back to weekly
                date_list = [today - timedelta(days=i)
                             for i in range(6, -1, -1)]
        elif period == 'weekly':
            date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
        else:  # monthly
            date_list = [today - timedelta(days=i) for i in range(29, -1, -1)]

        # Sales Trend
        sales_trend = []
        for date in date_list:
            daily_sales = Sale.objects.filter(
                company=company,
                invoice_date=date
            ).aggregate(total=Sum('grand_total'))
            sales_trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'amount': float(daily_sales['total'] or 0)
            })

        # Purchase Trend - Use same date_list as sales
        purchase_trend = []
        for date in date_list:
            daily_purchases = Purchase.objects.filter(
                company=company,
                invoice_date=date
            ).aggregate(total=Sum('grand_total'))
            purchase_trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'amount': float(daily_purchases['total'] or 0)
            })

        # Sales Due Trend (Last 7 days or 30 days)
        # Calculate outstanding amount (grand_total - paid_amount) for each day
        sales_due_trend = []
        if period == 'weekly':
            for i in range(6, -1, -1):
                date = today - timedelta(days=i)
                daily_dues = Sale.objects.filter(
                    company=company,
                    invoice_date=date
                ).annotate(
                    outstanding=F('grand_total') - F('paid_amount')
                ).filter(
                    outstanding__gt=0
                ).aggregate(total=Sum('outstanding', output_field=DecimalField()))
                sales_due_trend.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'amount': float(daily_dues['total'] or 0)
                })
        else:  # monthly
            for i in range(29, -1, -1):
                date = today - timedelta(days=i)
                daily_dues = Sale.objects.filter(
                    company=company,
                    invoice_date=date
                ).annotate(
                    outstanding=F('grand_total') - F('paid_amount')
                ).filter(
                    outstanding__gt=0
                ).aggregate(total=Sum('outstanding', output_field=DecimalField()))
                sales_due_trend.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'amount': float(daily_dues['total'] or 0)
                })

        # Purchase Due Trend - Use same date_list
        # Calculate outstanding amount (grand_total - paid_amount) for each day
        purchase_due_trend = []
        for date in date_list:
            daily_dues = Purchase.objects.filter(
                company=company,
                invoice_date=date
            ).annotate(
                outstanding=F('grand_total') - F('paid_amount')
            ).filter(
                outstanding__gt=0
            ).aggregate(total=Sum('outstanding', output_field=DecimalField()))
            purchase_due_trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'amount': float(daily_dues['total'] or 0)
            })

        # Customer Payment Trend - Use same date_list
        customer_payment_trend = []
        for date in date_list:
            daily_payments = Payment.objects.filter(
                company=company,
                payment_type=PaymentType.RECEIVED,
                date=date,
                status=PaymentStatus.COMPLETED
            ).aggregate(total=Sum('amount'))
            customer_payment_trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'amount': float(daily_payments['total'] or 0)
            })

        # Supplier Payment Trend - Use same date_list
        supplier_payment_trend = []
        for date in date_list:
            daily_payments = Payment.objects.filter(
                company=company,
                payment_type=PaymentType.MADE,
                date=date,
                status=PaymentStatus.COMPLETED
            ).aggregate(total=Sum('amount'))
            supplier_payment_trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'amount': float(daily_payments['total'] or 0)
            })

        # Product Sales date range (uses own period when product filter is applied)
        if product_ids and (product_sales_date_from and product_sales_date_to and product_sales_period == 'custom'):
            try:
                ps_start = datetime.strptime(product_sales_date_from, '%Y-%m-%d').date()
                ps_end = datetime.strptime(product_sales_date_to, '%Y-%m-%d').date()
                product_sales_date_list = []
                d = ps_start
                while d <= ps_end:
                    product_sales_date_list.append(d)
                    d += timedelta(days=1)
            except ValueError:
                product_sales_date_list = date_list
        elif product_ids and product_sales_period == 'monthly':
            product_sales_date_list = [today - timedelta(days=i) for i in range(29, -1, -1)]
        else:
            product_sales_date_list = date_list

        # Product Sales (from StockTransaction - base quantity)
        # Sales quantity trend: total qty sold per day (optional product filter)
        product_sales_base = Q(
            company=company,
            transaction_type='sale',
            direction='out'
        )
        if product_ids:
            product_sales_base &= Q(product_id__in=product_ids)

        product_sales_trend = []
        for date in product_sales_date_list:
            daily_qty = StockTransaction.objects.filter(
                product_sales_base,
                created_at__date=date
            ).aggregate(total=Sum('quantity'))
            product_sales_trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'quantity': float(daily_qty['total'] or 0)
            })

        # Top products by quantity sold (base unit) in the period
        product_sales_date_filter = product_sales_base & Q(
            created_at__date__gte=product_sales_date_list[0] if product_sales_date_list else today,
            created_at__date__lte=product_sales_date_list[-1] if product_sales_date_list else today
        )
        product_sales_agg = StockTransaction.objects.filter(
            product_sales_date_filter
        ).values('product__name', 'product__base_unit__name').annotate(
            total_quantity=Sum('quantity')
        ).order_by('-total_quantity')[:10]

        product_sales_by_product = [
            {
                'product_name': item['product__name'] or 'Unknown',
                'unit_name': item['product__base_unit__name'] or 'pcs',
                'total_quantity': float(item['total_quantity'] or 0)
            }
            for item in product_sales_agg
        ]

        # Low Stock Items
        low_stock = Stock.objects.filter(
            company=company,
            quantity__lt=10
        ).select_related('product', 'warehouse').values(
            'product__name',
            'warehouse__name',
            'quantity'
        )[:10]

        return Response({
            "message": "Dashboard statistics retrieved successfully",
            "data": {
                "sales": {
                    "today": {
                        "total": float(sales_today['total'] or 0),
                        "count": sales_today['count']
                    },
                    "month": {
                        "total": float(sales_month['total'] or 0),
                        "count": sales_month['count']
                    },
                    "pending_dues": float(pending_customer_dues['total'] or 0),
                    "trend": sales_trend,
                    "due_trend": sales_due_trend
                },
                "purchases": {
                    "today": {
                        "total": float(purchases_today['total'] or 0),
                        "count": purchases_today['count']
                    },
                    "month": {
                        "total": float(purchases_month['total'] or 0),
                        "count": purchases_month['count']
                    },
                    "supplier_outstanding": float(supplier_outstanding['total'] or 0),
                    "trend": purchase_trend,
                    "due_trend": purchase_due_trend
                },
                "customer_payments": {
                    "trend": customer_payment_trend
                },
                "supplier_payments": {
                    "trend": supplier_payment_trend
                },
                "product_sales": {
                    "trend": product_sales_trend,
                    "by_product": product_sales_by_product
                },
                "low_stock": list(low_stock)
            }
        }, status=status.HTTP_200_OK)
