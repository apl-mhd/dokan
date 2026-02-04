from django.urls import path
from . import views

app_name = "company"

urlpatterns = [
    path("", views.CompanyListCreateView.as_view(), name="company-list-create"),
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("users/create/", views.UserCreateView.as_view(), name="user-create"),
]
