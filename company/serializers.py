import json
from decimal import Decimal
from pathlib import Path

from rest_framework import serializers
from .models import User, Company, CompanyUser
from warehouse.models import Warehouse
from customer.models import Customer
from supplier.models import Supplier
from product.models import UnitCategory, Unit, Category


def _create_default_units_for_company(company: Company):
    """
    Create default unit categories + units for a newly registered company.
    Data source: `company/default_units.json`
    Safe to call multiple times (uses get_or_create/update).
    """
    path = Path(__file__).resolve().parent / "default_units.json"
    if not path.exists():
        return

    payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    categories = payload.get("unit_categories") or []

    for cat in categories:
        cat_name = (cat.get("name") or "").strip()
        if not cat_name:
            continue
        unit_category, _ = UnitCategory.objects.get_or_create(
            company=company, name=cat_name
        )

        units = cat.get("units") or []
        for u in units:
            unit_name = (u.get("name") or "").strip()
            if not unit_name:
                continue

            conversion_factor = Decimal(
                str(u.get("conversion_factor") or "1.0000"))
            is_base_unit = bool(u.get("is_base_unit", False))
            is_default = bool(u.get("is_default", False))

            unit_obj = Unit.objects.filter(
                company=company, unit_category=unit_category, name=unit_name
            ).first()
            if not unit_obj:
                unit_obj = Unit(
                    company=company,
                    unit_category=unit_category,
                    name=unit_name,
                )

            unit_obj.conversion_factor = conversion_factor
            unit_obj.is_base_unit = is_base_unit
            unit_obj.is_default = is_default
            unit_obj.is_active = True
            unit_obj.full_clean()
            unit_obj.save()


def _create_default_product_categories_for_company(company: Company):
    """
    Create default product categories for a newly registered company.
    Data source: `company/default_product_categories.json`
    Safe to call multiple times (uses get_or_create/update).
    """
    path = Path(__file__).resolve().parent / "default_product_categories.json"
    if not path.exists():
        return

    payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    categories = payload.get("product_categories") or []

    for c in categories:
        name = (c.get("name") or "").strip()
        if not name:
            continue
        description = c.get("description")
        obj, created = Category.objects.get_or_create(
            company=company,
            name=name,
            defaults={"description": description or None},
        )
        if not created:
            # Keep in sync with JSON (update description)
            obj.description = description or None
            obj.save(update_fields=["description"])


class RegisterSerializer(serializers.Serializer):
    """
    Public registration: creates User (username=phone), Company (phone, name),
    and CompanyUser. User is active but cannot access Django admin (is_staff=False).
    Easy passwords allowed (no complexity validation).
    """
    phone = serializers.CharField(max_length=255, trim_whitespace=True)
    email = serializers.EmailField(
        required=False, allow_blank=True, default="")
    business_name = serializers.CharField(max_length=255, source="name")
    password = serializers.CharField(
        max_length=128, write_only=True, style={"input_type": "password"}
    )

    def validate_phone(self, value):
        if not value:
            raise serializers.ValidationError("Phone number is required.")
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "This phone number is already registered."
            )
        if Company.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "This phone number is already registered."
            )
        return value

    def validate_email(self, value):
        value = (value or "").strip()
        if not value:
            return value
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "This email is already registered."
            )
        return value

    def validate_password(self, value):
        if not value or len(value) < 1:
            raise serializers.ValidationError("Password is required.")
        return value

    def create(self, validated_data):
        phone = validated_data["phone"]
        password = validated_data["password"]
        name = validated_data["name"]
        email = (validated_data.get("email") or "").strip()
        # Use placeholder so email is never blank (User model allows blank=True)
        user_email = email or f"{phone}@dokan.local"

        user = User.objects.create_user(
            username=phone,
            email=user_email,
            password=password,
            is_active=True,
            is_staff=False,  # no Django admin access
        )
        user.phone = phone
        user.save(update_fields=["phone"])
        company = Company.objects.create(
            name=name,
            phone=phone,
            owner=user,
            email=email or None,
        )
        CompanyUser.objects.create(company=company, user=user)
        # Create default warehouse for the new company
        Warehouse.objects.create(
            company=company,
            name="Warehouse 1",
            is_default=True,
            is_active=True,
        )
        # Create walk-in customer and supplier for the new company
        Customer.objects.create(
            company=company, name="Walk-in Customer", is_active=True)
        Supplier.objects.create(
            company=company, name="Walk-in Supplier", is_active=True)
        _create_default_units_for_company(company)
        _create_default_product_categories_for_company(company)
        return user


class UserListSerializer(serializers.ModelSerializer):
    """Read-only list of user fields for company user list."""

    class Meta:
        model = User
        fields = ("id", "username", "email",
                  "phone", "first_name", "last_name")
        read_only_fields = fields


class CompanyUserListSerializer(serializers.ModelSerializer):
    """Flattened company user list item (includes membership fields)."""

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    phone = serializers.CharField(
        source="user.phone", read_only=True, allow_null=True)
    first_name = serializers.CharField(
        source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)

    class Meta:
        model = CompanyUser
        fields = (
            "id",
            "user_id",
            "username",
            "email",
            "phone",
            "first_name",
            "last_name",
            "is_active",
        )
        read_only_fields = fields


class CompanyUserUpdateSerializer(serializers.ModelSerializer):
    """Update membership fields for a user inside a company."""

    class Meta:
        model = CompanyUser
        fields = ("is_active",)


class CompanyUserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Update a user's profile fields from company owner/staff context.
    Same uniqueness rules as ProfileSerializer, but works for arbitrary user instance.
    """

    class Meta:
        model = User
        fields = ("username", "email", "phone", "first_name", "last_name")

    def validate_username(self, value):
        if (
            User.objects.filter(username=value)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "A user with this username already exists."
            )
        return value

    def validate_email(self, value):
        value = (value or "").strip()
        if not value:
            return value
        if (
            User.objects.filter(email__iexact=value)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "This email is already registered.")
        return value

    def validate_phone(self, value):
        value = (value or "").strip() or None
        if not value:
            return value
        if (
            User.objects.filter(phone=value)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "This phone number is already in use.")
        return value


class ProfileSerializer(serializers.ModelSerializer):
    """Current user profile: username, email, phone, first_name, last_name."""

    class Meta:
        model = User
        fields = ("id", "username", "email",
                  "phone", "first_name", "last_name")
        read_only_fields = ("id",)

    def validate_username(self, value):
        if (
            User.objects.filter(username=value)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "A user with this username already exists."
            )
        return value

    def validate_email(self, value):
        value = (value or "").strip()
        if not value:
            return value
        if (
            User.objects.filter(email__iexact=value)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "This email is already registered."
            )
        return value

    def validate_phone(self, value):
        value = (value or "").strip() or None
        if not value:
            return value
        if (
            User.objects.filter(phone=value)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "This phone number is already in use."
            )
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        max_length=128, write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        max_length=128, write_only=True, style={"input_type": "password"}
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        if not value or len(value) < 1:
            raise serializers.ValidationError("New password is required.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class CompanyUserSetPasswordSerializer(serializers.Serializer):
    """Set another user's password (owner/staff only). No complexity rules."""

    new_password = serializers.CharField(
        max_length=128, write_only=True, style={"input_type": "password"}
    )

    def validate_new_password(self, value):
        if not value:
            raise serializers.ValidationError("New password is required.")
        return value


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "owner",
            "address",
            "phone",
            "email",
            "website",
            "is_active",
            "created_at",
        )
        read_only_fields = ("owner", "created_at")


class CompanyUpdateSerializer(serializers.ModelSerializer):
    """Update company details; validates phone uniqueness excluding current company."""

    class Meta:
        model = Company
        fields = ("id", "name", "address", "phone",
                  "email", "website", "is_active")
        read_only_fields = ("id",)

    def validate_phone(self, value):
        if not value:
            raise serializers.ValidationError("Phone number is required.")
        qs = Company.objects.filter(phone=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A company with this phone number already exists."
            )
        return value


class UserCreateSerializer(serializers.Serializer):
    """Create a user with password and assign to a company."""

    username = serializers.CharField(max_length=150, write_only=True)
    email = serializers.EmailField(
        required=False, allow_blank=True, default="", write_only=True
    )
    phone = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default="")
    password = serializers.CharField(
        max_length=128, write_only=True, style={"input_type": "password"}
    )
    first_name = serializers.CharField(
        max_length=150, required=False, default="")
    last_name = serializers.CharField(
        max_length=150, required=False, default="")
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), write_only=True
    )

    def validate_phone(self, value):
        value = (value or "").strip() or None
        if value and User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "This phone number is already in use.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "A user with this username already exists.")
        return value

    def validate_email(self, value):
        value = (value or "").strip()
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists.")
        return value or ""

    def validate_password(self, value):
        if not value:
            raise serializers.ValidationError("Password is required.")
        return value

    def create(self, validated_data):
        company = validated_data.pop("company_id")
        password = validated_data.pop("password")
        phone = (validated_data.pop("phone", "") or "").strip() or None
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=password,
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        if phone:
            user.phone = phone
            user.save(update_fields=["phone"])
        CompanyUser.objects.create(company=company, user=user)
        return user

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "username": instance.username,
            "email": instance.email,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
        }
