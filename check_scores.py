import os
import sys
import django

# Setup django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_year_project.settings')
django.setup()

from project_review.models import Company
from project_review.services.verification import calculate_investor_trust_score

print(f"{'ID':<5} | {'Name':<20} | {'GST Verified':<12} | {'GST Status':<12} | {'Old TS':<8} | {'New TS':<8}")
print("-" * 80)

for company in Company.objects.all():
    old_score = company.trust_score
    new_score = calculate_investor_trust_score(company)
    print(f"{company.id:<5} | {company.name[:20]:<20} | {str(company.gst_verified):<12} | {company.gst_verification_status:<12} | {old_score:<8} | {new_score:<8}")
