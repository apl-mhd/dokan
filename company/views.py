from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Company, CompanyUser
from .serializers import CompanySerializer, RegisterSerializer, UserCreateSerializer


class CompanyListCreateView(APIView):
    """List companies (for current user) or create a company (owner = current user)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        # Companies the user owns or is linked to via CompanyUser
        owned = Company.objects.filter(owner=request.user)
        linked = Company.objects.filter(
            company_users__user=request.user).distinct()
        companies = (owned | linked).distinct()
        serializer = CompanySerializer(companies, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CompanySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(owner=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(APIView):
    """
    Public registration: phone (required), email (optional), business name, password.
    Creates User (username=phone, is_active=True, is_staff=False), Company, and CompanyUser.
    """

    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(
            {"detail": "Registration successful. You can now log in with your phone number and password."},
            status=status.HTTP_201_CREATED,
        )


class UserCreateView(APIView):
    """
    Create a user with password and assign to a company.
    Only staff/superuser or company owner can create users for that company.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        company = serializer.validated_data["company_id"]
        # Allow if requester is staff/superuser or owner of the company
        if not (
            request.user.is_staff
            or request.user.is_superuser
            or company.owner_id == request.user.id
        ):
            return Response(
                {"detail": "You can only add users to companies you own."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = serializer.save()
        return Response(
            UserCreateSerializer().to_representation(user),
            status=status.HTTP_201_CREATED,
        )
