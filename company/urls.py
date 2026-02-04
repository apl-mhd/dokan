from django.urls import path
from . import views

app_name = "company"

urlpatterns = [
    path("", views.CompanyListCreateView.as_view(), name="company-list-create"),
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("profile/change-password/",
         views.ChangePasswordView.as_view(), name="change-password"),
    path("company/current/", views.CurrentCompanyView.as_view(),
         name="company-current"),
    path("users/", views.CompanyUserListView.as_view(), name="company-user-list"),
    path("users/<int:user_id>/", views.CompanyUserDetailView.as_view(),
         name="company-user-detail"),
    path("users/<int:user_id>/profile/", views.CompanyUserProfileView.as_view(),
         name="company-user-profile"),
    path("users/create/", views.UserCreateView.as_view(), name="user-create"),
]
