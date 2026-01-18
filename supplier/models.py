from django.db import models
from core.models import Party

# Create your models here.
class SupplierManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_supplier=True)

class Supplier(Party):
    objects = SupplierManager()
    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.is_supplier = True
        super().save(*args, **kwargs)