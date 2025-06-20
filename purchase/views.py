from django.shortcuts import renderPurchaseAPIView
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response


# Create your views here.


class (APIView):
    def get(self, request):
        # Here you can implement your logic to fetch purchase data
        data = {
            "message": "This is a sample response from the Purchase API."
        }
        return Response(data)

    def post(self, request):
        # Here you can implement your logic to handle purchase creation
        data = request.data
        return Response({"message": "Purchase created successfully!", "data": data})

def test(request):
    return HttpResponse("Purchase app is working fine!")
