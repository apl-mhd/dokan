from django.utils.deprecation import MiddlewareMixin
from .models import CompanyUser


class CompanyMiddleware(MiddlewareMixin):
    """
    Middleware to attach company to request object for multi-tenant support.
    """
    def process_request(self, request):
        request.company = None
        
        if request.user and request.user.is_authenticated:
            # Get company from CompanyUser relationship
            company_user = CompanyUser.objects.filter(user=request.user).first()
            if company_user:
                request.company = company_user.company
            # Fallback: check if user owns a company
            elif hasattr(request.user, 'company_set'):
                request.company = request.user.company_set.first()

