from rest_framework import serializers
from .models import User, Company, CompanyUser
from warehouse.models import Warehouse


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
        return user


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


class UserCreateSerializer(serializers.Serializer):
    """Create a user with password and assign to a company."""

    username = serializers.CharField(max_length=150, write_only=True)
    email = serializers.EmailField(write_only=True)
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

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "A user with this username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        company = validated_data.pop("company_id")
        password = validated_data.pop("password")
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=password,
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
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
