import os
import sys
import django

# Setup django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_year_project.settings')
django.setup()

from project_review.models import Company

for c in Company.objects.all():
    print(f"ID: {c.id} | Name: {c.name} | GST: {c.gst_verification_status} | TS: {c.trust_score}")
