import os
import django
from django.conf import settings
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from unittest.mock import MagicMock

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dokan.settings.base')
django.setup()

from company.middleware import CompanyMiddleware
from company.models import CompanyUser, Company

def verify_fix():
    print("Verifying CompanyMiddleware fix...")
    
    factory = RequestFactory()
    request = factory.get('/')
    
    # Simulate initial state: User is not yet authenticated by DRF
    # In standard Django, AuthenticationMiddleware sets request.user to AnonymousUser
    request.user = AnonymousUser()
    
    middleware = CompanyMiddleware(get_response=lambda r: None)
    
    # Run process_request
    middleware.process_request(request)
    
    print(f"Type of request.company: {type(request.company)}")
    
    # Now simulate DRF authenticating the user LATER
    # We need a mock user and company
    mock_user = MagicMock()
    mock_user.is_authenticated = True
    
    mock_company = MagicMock()
    mock_company.name = "Test Company"
    
    # Mock the database lookup in get_user_company
    # Since we can't easily rely on DB state, we'll patch the get_user_company function or mocking objects.
    # However, since we define get_user_company in middleware.py, and it imports models.
    # Let's try to mock the models imports in middleware.py if possible, or just rely on the logic.
    
    # Actually, simpler: we can just Mock the logic inside get_user_company if we patch it?
    # Or better yet, we can trust the logic if we just mock the DB calls?
    
    # Let's mock the ORM calls.
    # We'll use unittest.mock.patch
    from unittest.mock import patch
    
    with patch('company.middleware.CompanyUser.objects.filter') as mock_filter:
        # Setup mock return
        mock_company_user = MagicMock()
        mock_company_user.company = mock_company
        mock_filter.return_value.first.return_value = mock_company_user
        
        # ACTUALLY set the user on the request object, simulating what DRF does
        request.user = mock_user
        
        # Access request.company to trigger evaluation
        print("Accessing request.company...")
        company = request.company
        
        print(f"Resolved company: {company}")
        
        if company == mock_company:
            print("SUCCESS: Company resolved correctly after late authentication!")
        else:
            print("FAILURE: Company did not resolve correctly.")

if __name__ == "__main__":
    verify_fix()
