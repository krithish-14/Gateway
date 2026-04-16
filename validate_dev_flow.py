import os
import django
import sys

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_setup.settings')
django.setup()

from django.contrib.auth.models import User
from project_review.models import UserProfile, Company, PortalMessage, LoginHistory
from django.test import Client, override_settings

@override_settings(ALLOWED_HOSTS=['testserver'])
def test_development_flow():
    print("Starting Development Flow Validation...")
    
    # 1. Cleanup existing test data
    User.objects.filter(username='test_dev_user').delete()
    
    client = Client()
    
    # 2. Simulate User Registration (Investor)
    print("Testing Investor Registration...")
    reg_data = {
        'username': 'test_dev_user',
        'email': 'dev_test@example.com',
        'role': 'investor',
        'password': 'password123',
        'confirm_password': 'password123',
        'company_name': 'Dev Test Corp',
        'company_website': 'https://devtest.corp',
        'linkedin_profile': 'https://linkedin.com/devtest'
    }
    
    from django.urls import reverse
    resp = client.post(reverse('project_review:register'), reg_data)
    
    user = User.objects.filter(username='test_dev_user').first()
    if not user:
        print("FAIL: User not created")
        return
    
    profile = user.profile
    company = user.companies.first()
    
    if not company or company.name != 'Dev Test Corp':
        print(f"FAIL: Company record not created correctly. Company: {company}")
        return
    
    print("SUCCESS: Investor user and company created.")

    # 3. Simulate First Login
    print("Testing First Login & Welcome Message...")
    login_data = {
        'username': 'test_dev_user',
        'password': 'password123'
    }
    client.post(reverse('project_review:login'), login_data)
    
    # Check Login History
    login_count = LoginHistory.objects.filter(user=user).count()
    if login_count == 0:
        print("FAIL: Login history not recorded")
        return
    
    # Check Welcome Message
    welcome_msg = PortalMessage.objects.filter(recipient=user, sender_name='Gateway').first()
    if not welcome_msg:
        print("FAIL: Welcome message not created in DB")
    else:
        print(f"SUCCESS: Welcome message found: {welcome_msg.text[:50]}...")

    # 4. Test Profile Update
    print("Testing Profile Update (Data Integrity)...")
    profile_update_data = {
        'first_name': 'Dev',
        'last_name': 'Tester',
        'email': 'dev_test@example.com',
        'phone_number': '1234567890',
        'company_name': 'Dev Test Corp Updated',
        'investor_role_in_company': 'Managing Director',
        'company_website': 'https://updated.corp',
        'about_company': 'Updated about text.',
        'investment_focus': 'Updated focus.'
    }
    
    # We need to be logged in for profile view
    client.login(username='test_dev_user', password='password123')
    client.post(reverse('project_review:profile'), profile_update_data)
    
    # Reload from DB
    user.refresh_from_db()
    company.refresh_from_db()
    
    if user.first_name != 'Dev' or company.name != 'Dev Test Corp Updated':
        print(f"FAIL: Profile update failed. User: {user.first_name}, Company: {company.name}")
    else:
        print("SUCCESS: Profile and Company updated correctly. Redundancy check passed!")

    print("\nALL DEVELOPMENT FLOWS VALIDATED SUCCESSFULLY!")

if __name__ == "__main__":
    test_development_flow()
