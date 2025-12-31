from .models import Purchase, PurchaseItem
from product.models import Unit
from .serializers import PurchaseSerializer, PurchaseItemCreatSerializer, PurchaseCreateSerializer, ItemSerializer
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Prefetch
from purchase.services.purchase_service import create_purchase_with_items, update_purchase_with_items
from product.models import Product
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status, viewsets, filters
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.models import User
from django.db import transaction, IntegrityError
import uuid
from .services.purchase_service import PurchaseService
import django_filters 

# Create your views here.


class CustomSearchFilter(filters.SearchFilter):
    def get_search_fields(self, view, request):
        if request.query_params.get('inv'):
            return ['invoice_number']
        return super().get_search_fields(view, request)
    
class ApplicationFilter(django_filters.FilterSet):
    start_date = django_filters.CharFilter(field_name='invoice_number', lookup_expr='')

    class Meta:
        model = Purchase
        fields = ['invoice_number']

class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['invoice_date']
    ordering = ['-invoice_date']


class PurchaseAPIView(APIView):
    def get(self, request):
        purchase = Purchase.objects.all()
        serializer = PurchaseSerializer(purchase, many=True)
        return Response({"message": "Purchase API", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data

        user = User.objects.first()

        try:
            purchase = PurchaseService.create_purchase(data, user)
            return Response({"message": "Purchase Create successfully"}, status=status.HTTP_201_CREATED)
        
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except IntegrityError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)  

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request):
        return Response({"message": "Purchase API"}, status=status.HTTP_200_OK)

    def delete(self, request):
        return Response({"message": "Purchase API"}, status=status.HTTP_200_OK)



class _PurchaseAPIView(APIView):
    # permission_classes = [IsAuthenticated]  # Allow any user to access this API

    def get(self, request):

        purchase = Purchase.objects.select_related(
            'supplier').prefetch_related(Prefetch('items', queryset=PurchaseItem.objects.select_related('product', 'unit'))).all().order_by('-created_at')
        serializer = PurchaseSerializer(purchase, many=True)

        return Response({"message": "Purchasse Response", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data

        serializer = PurchaseCreateSerializer(data=data)
        if serializer.is_valid():

            try:
                with transaction.atomic():
            
                    user = User.objects.first()  # Replace with actual user retrieval logic
                    validated_data = serializer.validated_data
                    items = validated_data.pop('items', [])

                    purchase = Purchase.objects.create(**validated_data, created_by=user)

                    grand_total = 0

                
                    p = []
                    for i in items:

                        quantity = i['quantity']
                        unit_price = i['unit_price']
                        line_total = quantity * unit_price
                        grand_total += line_total
                        p.append(PurchaseItem(
                            purchase=purchase,
                            product=i['product'],
                            quantity=i['quantity'],
                                unit=i['unit'],
                                unit_price=unit_price,
                                line_total=line_total
                            ))
                    PurchaseItem.objects.bulk_create(p)
                    purchase.update(grand_total=grand_total)
                    # purchase.grand_total = grand_total
                    # purchase.save()
                    
                return Response({"message": "Purchase created successfully!", "data": serializer.data}, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({"error": str(e)}, status=500)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # try:
        #     with transaction.atomic():
        #         purchase = create_purchase_with_items(data, request.user)
        #         serailizer = PurchaseSerializer(purchase)
        #         return Response({"message": "Purchase created successfully!", "data": serailizer.data}, status=status.HTTP_201_CREATED)

        # except Exception as e:
        #     return Response({"error": str(e)}, status=500)

    def put(self, request, pk):
        data = request.data
        try:
            with transaction.atomic():

                purchase = update_purchase_with_items(pk, data, request.user)
                serializer = PurchaseSerializer(purchase)

            
                if serializer.is_valid():
                    user = User.objects.first()
                    purchase = get_object_or_404(Purchase, pk=pk)
                    purchase.items.all().delete()

                    items = []
                    grand_total = 0
                    for i in purchase.get('items', []):
                        
                        line_total = i.quantity * i.unit_price
                        grand_total = grand_total + line_total
                        items.append(
                            PurchaseItem(
                                purchase=purchase,
                                product=i.product,
                                quantity=i.quantity,
                                unit=i.unit,
                                unit_price=i.unit_price,
                                line_total = line_total
                                ))


                    PurchaseItem.objects.bulk_create(items)
                    purchase.grand_total = grand_total

                return Response({"message": "Purchase updated successfully!", "data": serializer.data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def delete(self, request, pk):
        try:
            purchase = get_object_or_404(Purchase, id=pk)
            purchase.delete()
            return Response({"message": "Purchase deleted successfully!"}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


def test(request):

    product = get_object_or_404(Product, id=1)
    product.update(name='update katari')

    return HttpResponse("Purchase app is working fine!")
