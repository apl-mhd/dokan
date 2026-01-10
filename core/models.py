from django.db import models
from company.models import Company
from datetime import datetime

# Create your models here.


class Person(models.Model):
    name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(blank=True,  null=True, max_length=20)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class DocumentType(models.TextChoices):
    PURCHASE_ORDER = 'purchase_order', 'Purchase Order'
    PURCHASE_RETURN = 'purchase_return', 'Purchase Return'
    SALES_ORDER = 'sales_order', 'Sales Order'
    SALES_RETURN = 'sales_return', 'Sales Return'


class DocumentSequence(models.Model):
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    current_year = models.IntegerField(default=datetime.now().year)
    next_number = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('company', 'document_type', 'current_year')

    def __str__(self):
        return f"{self.company.name} - {self.document_type} - {self.next_number}"