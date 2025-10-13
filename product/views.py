from django.shortcuts import render
from rest_framework import viewsets
from .serializers import ProductSerializer, UnitSerializer
# Create your views here.



class UnitModelSerializer(viewsets.ModelViewSet):
    queryset = UnitSerializer
    serializer_class = UnitSerializer
   


