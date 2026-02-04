"""
Custom authentication backend so users can log in with username, email, or phone.
"""
from .models import User


class UsernameEmailPhoneBackend:
    """
    Authenticate using username, email, or phone (all passed as 'username' from login).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        username = username.strip()
        user = (
            User.objects.filter(username=username).first()
            or User.objects.filter(email__iexact=username).first()
            or User.objects.filter(phone=username).first()
        )
        if user and user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
