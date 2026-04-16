"""
Management command: reverify_investors
Runs the investor verification pipeline on every Company record.
"""
from django.core.management.base import BaseCommand
from project_review.models import Company
from project_review.services import verification as svc
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Re-run verification on all (or a specific) investor companies."

    def add_arguments(self, parser):
        parser.add_argument(
            '--id', type=int, default=None,
            help='PK of a specific Company to re-verify (omit for all).'
        )

    def handle(self, *args, **options):
        pk = options.get('id')
        qs = Company.objects.filter(pk=pk) if pk else Company.objects.all()
        total = qs.count()
        
        self.stdout.write(f"Re-verifying {total} investor company(s)…")

        ok = 0
        for company in qs:
            try:
                self.stdout.write(f"  Processing [{company.id}] {company.name}...")
                
                # 1. LinkedIn
                if company.linkedin_profile:
                    res_li = svc.verify_linkedin(company.linkedin_profile)
                    company.linkedin_verified = res_li.get('verified', False)

                # 2. Website
                if company.website:
                    res_ws = svc.verify_website(company.website)
                    company.website_verified = res_ws.get('verified', False)
                    company.website_status = res_ws.get('status', 'Unknown')

                # 3. GST
                if company.gst_invoice:
                    res_gst = svc.verify_gstin(company.gst_invoice, gstin_override=company.gstin_number)
                    company.gst_verified = res_gst.get('verified', False)
                    company.gst_verification_status = res_gst.get('status', 'Not Uploaded')
                    company.gstin_number = res_gst.get('gstin', '')
                    
                    # Update metadata
                    gst_data = res_gst.get('data', {})
                    if gst_data:
                        company.gst_legal_name = gst_data.get('legal_name', '')
                        company.gst_registration_date = gst_data.get('registration_date', '')
                        company.gst_center_state = gst_data.get('state_code', '')
                        company.gst_taxpayer_type = gst_data.get('taxpayer_type', '')
                else:
                    company.gst_verification_status = 'Not Uploaded'
                    company.gst_verified = False

                # 4. Scores & Status Labelling
                company.trust_score = svc.calculate_investor_trust_score(company)
                company.verification_status = svc.get_verification_status_label(company.trust_score)

                company.save()
                ok += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"    → GST: {company.gst_verification_status} | "
                        f"Score: {company.trust_score} | Status: {company.verification_status}"
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"    → FAILED: {e}")
                )

        self.stdout.write(self.style.SUCCESS(f"\nDone. {ok}/{total} records updated."))
