from django.db import models
from core.models import Person

# Create your models here.


class Supplier(Person):
    pass

    def __str__(self):
        return self.name
