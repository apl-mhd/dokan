from django.db import models

# Create your models here.
from core.models import Party
class CustomerManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_customer=True)

class Customer(Party):
    objects = CustomerManager()
    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.is_customer = True
        super().save(*args, **kwargs)

# class Customer(Person):
#     pass

#     def __str__(self):
#         return self.name
