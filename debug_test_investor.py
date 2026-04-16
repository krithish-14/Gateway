import os
import sys
import django

# Setup django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_year_project.settings')
django.setup()

from project_review.models import Company

print(f"{'ID':<5} | {'Name':<25} | {'LI':<6} | {'WS':<6} | {'GST V':<8} | {'GST S':<12} | {'Admin':<6} | {'TS'}")
print("-" * 90)

for c in Company.objects.filter(name__icontains='test'):
    print(f"{c.id:<5} | {c.name[:25]:<25} | {str(c.linkedin_verified):<6} | {str(c.website_verified):<6} | {str(c.gst_verified):<8} | {c.gst_verification_status:<12} | {str(c.admin_approved):<6} | {c.trust_score}")
