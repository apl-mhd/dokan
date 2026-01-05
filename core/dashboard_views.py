from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from purchase.models import Purchase
from sale.models import Sale
from inventory.models import Stock


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
        
        pending_customer_dues = Sale.objects.filter(
            company=company,
            status='pending'
        ).aggregate(
            total=Sum('grand_total')
        )
        
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
        
        supplier_outstanding = Purchase.objects.filter(
            company=company,
            status='pending'
        ).aggregate(
            total=Sum('grand_total')
        )
        
        # Sales Trend (Last 7 days)
        sales_trend = []
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            daily_sales = Sale.objects.filter(
                company=company,
                invoice_date=date
            ).aggregate(total=Sum('grand_total'))
            sales_trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'amount': float(daily_sales['total'] or 0)
            })
        
        # Purchase Trend (Last 7 days)
        purchase_trend = []
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            daily_purchases = Purchase.objects.filter(
                company=company,
                invoice_date=date
            ).aggregate(total=Sum('grand_total'))
            purchase_trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'amount': float(daily_purchases['total'] or 0)
            })
        
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
                    "trend": sales_trend
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
                    "trend": purchase_trend
                },
                "low_stock": list(low_stock)
            }
        }, status=status.HTTP_200_OK)

