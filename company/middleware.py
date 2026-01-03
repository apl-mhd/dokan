from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject
from .models import CompanyUser


def get_user_company(request):
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return None

    # Get company from CompanyUser relationship
    company_user = CompanyUser.objects.filter(user=request.user).first()
    if company_user:
        return company_user.company
    
    # Fallback: check if user owns a company
    if hasattr(request.user, 'company_set'):
        return request.user.company_set.first()
    
    return None


class CompanyMiddleware(MiddlewareMixin):
    """
    Middleware to attach company to request object for multi-tenant support.
    Uses SimpleLazyObject to defer evaluation until after authentication (DRF).
    """
    def process_request(self, request):

        request.company = SimpleLazyObject(lambda: get_user_company(request))

