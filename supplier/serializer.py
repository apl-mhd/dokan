from rest_framework import serializers
from .models import Supplier


class SupplierSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = Supplier
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'balance', 'company']

    def validate_name(self, value):
        """Validate supplier name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Supplier name cannot be empty.")
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Supplier name must be at least 2 characters long.")
        return value.strip()

    def validate_email(self, value):
        """Validate email format if provided"""
        if value:
            # Basic email validation - Django's EmailField already handles this, but we add custom message
            if '@' not in value:
                raise serializers.ValidationError("Enter a valid email address.")
        return value

    def validate_phone(self, value):
        """Validate phone number - required field"""
        if not value or not value.strip():
            raise serializers.ValidationError("Phone number is required.")
        
        # Remove common phone number characters for validation
        cleaned_phone = value.replace(' ', '').replace('-', '').replace('+', '').replace('(', '').replace(')', '')
        if not cleaned_phone.isdigit():
            raise serializers.ValidationError("Phone number must contain only digits and common formatting characters.")
        if len(cleaned_phone) < 10:
            raise serializers.ValidationError("Phone number must be at least 10 digits long.")
        return value

    def validate(self, attrs):
        """Validate that phone number is unique within the company"""
        phone = attrs.get('phone')
        
        # Get company from context if available
        company = None
        request = self.context.get('request', None) if self.context else None
        if request and hasattr(request, 'company'):
            company = request.company
        
        # Skip validation if phone is empty or company is not available
        if not phone or not company:
            return attrs
        
        # Check for existing party with same phone and company
        from core.models import Party
        queryset = Party.objects.filter(company=company, phone=phone)
        
        # Exclude current instance if updating
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            existing_party = queryset.first()
            party_type = 'customer' if existing_party.is_customer else 'supplier' if existing_party.is_supplier else 'party'
            raise serializers.ValidationError({
                'phone': f'This phone number is already registered to a {party_type} ({existing_party.name}). Phone numbers must be unique within your company.'
            })
        
        return attrs

    def validate_opening_balance(self, value):
        """Validate opening balance"""
        if value is None:
            return 0.00
        return value

    def validate_credit_limit(self, value):
        """Validate credit limit"""
        if value is None:
            return 0.00
        if value < 0:
            raise serializers.ValidationError("Credit limit cannot be negative.")
        return value
