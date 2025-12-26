from django.db import models
from django.utils import timezone
from customer.models import Customer
from supplier.models import Supplier

# Create your models here.


class BasePayment(models.Model):

    METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('cheque', 'Cheque'),
        ('others', 'Others'),
    ]

    payment_method = models.CharField(
        max_length=50, choices=METHOD_CHOICES, null=True, blank=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(null=True, blank=True)
    reference_number = models.CharField(max_length=100) # Cheque # or TRX ID


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        abstract = True



class CustomerPayment(BasePayment):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)

class SupplierPayment(BasePayment):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)

# class _Payment(models.Model):
#     PAYMENT_TYPE_CHOICES = [
#         ('incoming', 'Incoming'),   # from customers
#         ('outgoing', 'Outgoing'),   # to suppliers
#     ]

#     METHOD_CHOICES = [
#         ('cash', 'Cash'),
#         ('bank', 'Bank Transfer'),
#         ('bkash', 'bKash'),
#         ('nagad', 'Nagad'),
#         ('cheque', 'Cheque'),
#         ('others', 'Others'),
#     ]


#     payment_method = models.CharField(
#         max_length=50, choices=METHOD_CHOICES, null=True, blank=True)
#     payment_type = models.CharField(
#         max_length=10, choices=PAYMENT_TYPE_CHOICES)
#     amount = models.DecimalField(max_digits=10, decimal_places=2)
#     date = models.DateTimeField(auto_now_add=True)

#     customer = models.ForeignKey(
#         'customer.Customer', on_delete=models.CASCADE, null=True, blank=True)
#     supplier = models.ForeignKey(
#         'supplier.Supplier', on_delete=models.CASCADE, null=True, blank=True)

#     method = models.CharField(max_length=50)
#     status = models.CharField(max_length=50)
#     notes = models.TextField(null=True, blank=True)
#     created_by = models.ForeignKey(
#         'auth.User', on_delete=models.CASCADE, related_name='payment_created_by')
#     updated_by = models.ForeignKey(
#         'auth.User', on_delete=models.CASCADE, related_name='payment_updated_by')
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return f"{self.method} - {self.amount} - {self.status}"
