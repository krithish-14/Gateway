import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_setup.settings')
django.setup()

from django.contrib.auth.models import User
from project_review.models import UserProfile, Company

try:
    user = User.objects.get(username='test_investor')
    
    # Update UserProfile
    profile, created = UserProfile.objects.get_or_create(user=user)
    profile.role = UserProfile.ROLE_INVESTOR
    profile.save()
    
    # Update Company details (where the actual data resides for investors)
    company = Company.objects.filter(user=user).first()
    if not company:
        company = Company(user=user)
    
    company.name = "Global Ventures Inc."
    company.about = "Leading investment firm for startups."
    company.investment_focus = "Tech and AI"
    company.role_in_company = "Managing Director"
    company.save()
    
    print("Updated test_investor profile and company details successfully.")
except User.DoesNotExist:
    print("Error: test_investor user not found.")
except Exception as e:
    print(f"Error: {e}")
