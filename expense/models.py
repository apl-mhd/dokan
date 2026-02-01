from django.db import models
from company.models import Company
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class ExpenseCategory(models.Model):
    """Category for grouping expenses (e.g. Rent, Utilities, Salaries)."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='expense_categories')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ('company', 'name')

    def __str__(self):
        return self.name


class Expense(models.Model):
    """Single expense entry linked to a category."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name='expenses'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    date = models.DateField(db_index=True)
    description = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_expenses'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.category.name} - {self.amount} ({self.date})"
