from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Company, CompanyUser
from .serializers import (
    ChangePasswordSerializer,
    CompanySerializer,
    CompanyUpdateSerializer,
    CompanyUserListSerializer,
    CompanyUserUpdateSerializer,
    CompanyUserProfileUpdateSerializer,
    ProfileSerializer,
    RegisterSerializer,
    UserCreateSerializer,
)


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


class ProfileView(APIView):
    """GET or PATCH current user profile (username, email, first_name, last_name)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = ProfileSerializer(
            request.user, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """POST to change current user password (old_password, new_password)."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response({"detail": "Password updated successfully."})


class CurrentCompanyView(APIView):
    """GET or PATCH the current user's company (from request.company)."""

    permission_classes = (IsAuthenticated,)

    def get_company(self, request):
        if not hasattr(request, "company") or not request.company:
            return None
        return request.company

    def get(self, request):
        company = self.get_company(request)
        if not company:
            return Response(
                {"detail": "No company associated with your account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CompanyUpdateSerializer(company)
        return Response(serializer.data)

    def patch(self, request):
        company = self.get_company(request)
        if not company:
            return Response(
                {"detail": "No company associated with your account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CompanyUpdateSerializer(
            company, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class CompanyUserListView(APIView):
    """List users for the current company (from request.company)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        company = getattr(request, "company", None)
        if not company:
            return Response(
                {"detail": "No company associated with your account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        company_users = CompanyUser.objects.filter(
            company=company
        ).select_related("user").order_by("user__username")
        serializer = CompanyUserListSerializer(company_users, many=True)
        return Response(serializer.data)


class CompanyUserDetailView(APIView):
    """
    Update or remove a user's membership from the current company.
    Only staff/superuser or company owner can perform actions.
    """

    permission_classes = (IsAuthenticated,)

    def _get_company_user(self, request, user_id: int):
        company = getattr(request, "company", None)
        if not company:
            return None, Response(
                {"detail": "No company associated with your account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            company_user = CompanyUser.objects.select_related("company", "user").get(
                company=company, user_id=user_id
            )
        except CompanyUser.DoesNotExist:
            return None, Response(
                {"detail": "User not found in this company."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return company_user, None

    def _check_owner(self, request, company):
        return request.user.is_staff or request.user.is_superuser or company.owner_id == request.user.id

    def patch(self, request, user_id: int):
        company_user, error = self._get_company_user(request, user_id)
        if error:
            return error
        if not self._check_owner(request, company_user.company):
            return Response(
                {"detail": "You can only manage users in companies you own."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if company_user.company.owner_id == company_user.user_id:
            return Response(
                {"detail": "You cannot deactivate the company owner."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CompanyUserUpdateSerializer(
            company_user, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(CompanyUserListSerializer(company_user).data)

    def delete(self, request, user_id: int):
        company_user, error = self._get_company_user(request, user_id)
        if error:
            return error
        if not self._check_owner(request, company_user.company):
            return Response(
                {"detail": "You can only manage users in companies you own."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if company_user.company.owner_id == company_user.user_id:
            return Response(
                {"detail": "You cannot remove the company owner."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        company_user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CompanyUserProfileView(APIView):
    """PATCH a company user's profile (owner/staff only)."""

    permission_classes = (IsAuthenticated,)

    def patch(self, request, user_id: int):
        company = getattr(request, "company", None)
        if not company:
            return Response(
                {"detail": "No company associated with your account."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not (
            request.user.is_staff
            or request.user.is_superuser
            or company.owner_id == request.user.id
        ):
            return Response(
                {"detail": "You can only manage users in companies you own."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not CompanyUser.objects.filter(company=company, user_id=user_id).exists():
            return Response(
                {"detail": "User not found in this company."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            user = CompanyUser.objects.select_related("user").get(
                company=company, user_id=user_id
            ).user
        except CompanyUser.DoesNotExist:
            return Response(
                {"detail": "User not found in this company."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CompanyUserProfileUpdateSerializer(
            user, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(ProfileSerializer(user).data)


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
