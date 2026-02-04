from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Custom user model for multi-tenant support.
    Users are linked to companies via CompanyUser.
    """
    email = models.EmailField(blank=True)  # require email

    class Meta:
        db_table = "company_user"  # avoid clash with join table name
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.username


class Company(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_companies",
    )
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=255, unique=True)
    email = models.EmailField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to="company/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name


class CompanyUser(models.Model):
    """
    Links a user to a company. A user can belong to one or more companies.
    """
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_users"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_users",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("company", "user")
        verbose_name = "Company user"
        verbose_name_plural = "Company users"

    def __str__(self):
        return f"{self.user.username} @ {self.company.name}"
