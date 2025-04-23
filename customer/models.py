from django.db import models

# Create your models here.
from core.models import Person


class Customer(Person):
    pass

    def __str__(self):
        return self.name
