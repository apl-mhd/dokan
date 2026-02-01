from product.models import Product, Unit, UnitCategory, Category
from rest_framework import serializers


class CategorySerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ['company', 'created_at', 'updated_at']


class UnitCategorySerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = UnitCategory
        fields = '__all__'
        read_only_fields = ['company', 'created_at', 'updated_at']


class UnitSerializer(serializers.ModelSerializer):
    unit_category_name = serializers.CharField(
        source='unit_category.name', read_only=True)

    class Meta:
        model = Unit
        fields = '__all__'
        read_only_fields = ['company', 'created_at', 'updated_at']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source='category.name', read_only=True)
    base_unit_name = serializers.CharField(
        source='base_unit.name', read_only=True)
    company_name = serializers.CharField(
        source='company.name', read_only=True)

    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['company', 'created_at', 'updated_at']


class ProductCreateInputSerializer(serializers.Serializer):
    """Serializer for creating a product"""
    name = serializers.CharField(max_length=128, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.IntegerField(required=True)
    base_unit = serializers.IntegerField(required=False, allow_null=True)
    purchase_price = serializers.DecimalField(
        max_digits=12, decimal_places=4, required=False, default=0)
    selling_price = serializers.DecimalField(
        max_digits=12, decimal_places=4, required=False, default=0)

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Product name cannot be empty.")
        return value.strip()


class ProductUpdateInputSerializer(serializers.Serializer):
    """Serializer for updating a product"""
    name = serializers.CharField(max_length=128, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.IntegerField(required=False)
    base_unit = serializers.IntegerField(required=False, allow_null=True)
    purchase_price = serializers.DecimalField(
        max_digits=12, decimal_places=4, required=False)
    selling_price = serializers.DecimalField(
        max_digits=12, decimal_places=4, required=False)


class UnitCreateInputSerializer(serializers.Serializer):
    """Serializer for creating a unit"""
    name = serializers.CharField(max_length=50, required=True)
    conversion_factor = serializers.DecimalField(
        max_digits=10, decimal_places=4, required=True)
    is_base_unit = serializers.BooleanField(required=False, default=False)
    unit_category = serializers.IntegerField(required=False, allow_null=True)

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Unit name cannot be empty.")
        return value.strip()

    def validate_conversion_factor(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Conversion factor must be greater than zero.")
        return value


class UnitUpdateInputSerializer(serializers.Serializer):
    """Serializer for updating a unit"""
    name = serializers.CharField(max_length=50, required=False)
    conversion_factor = serializers.DecimalField(
        max_digits=10, decimal_places=4, required=False)
    is_base_unit = serializers.BooleanField(required=False)
    unit_category = serializers.IntegerField(required=False, allow_null=True)


class UnitCategoryCreateInputSerializer(serializers.Serializer):
    """Serializer for creating a unit category"""
    name = serializers.CharField(max_length=50, required=True)

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Unit category name cannot be empty.")
        return value.strip()


class UnitCategoryUpdateInputSerializer(serializers.Serializer):
    """Serializer for updating a unit category"""
    name = serializers.CharField(max_length=50, required=False)
