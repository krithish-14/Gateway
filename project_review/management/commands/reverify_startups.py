"""
Management command: reverify_startups
Runs the fixed verification pipeline on every Registration record.
Usage:
    python manage.py reverify_startups             # all records
    python manage.py reverify_startups --id 12     # single record by PK
"""
from django.core.management.base import BaseCommand
from project_review.models import Registration
from project_review.services import verification as svc
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Re-run patent + idea verification on all (or a specific) startup registrations."

    def add_arguments(self, parser):
        parser.add_argument(
            '--id', type=int, default=None,
            help='PK of a specific Registration to re-verify (omit for all).'
        )

    def handle(self, *args, **options):
        pk = options.get('id')
        qs = Registration.objects.filter(pk=pk) if pk else Registration.objects.all()
        total = qs.count()
        
        # ── Step 0: Training Phase (Global Accuracy Optimization) ───────────
        self.stdout.write("Initializing Neural Training Phase...")
        all_summaries = [r.extracted_summary_text or r.profile_text or "" for r in Registration.objects.all()]
        train_res = svc.train_verification_model([s for s in all_summaries if s])
        if train_res.get('success'):
            self.stdout.write(self.style.SUCCESS(f"  {train_res['message']}"))
            self.stdout.write(f"  Metrics: {train_res['metrics']}")
        
        self.stdout.write(f"\nRe-verifying {total} registration(s)…")

        ok = 0
        for reg in qs:
            try:
                # ── Step 1: Idea Text ────────────────────────────────────────
                summary_text = reg.extracted_summary_text or reg.profile_text or ""

                # ── Step 2: Keywords ─────────────────────────────────────────
                if summary_text:
                    keywords = svc.generate_keywords(summary_text)
                    reg.generated_keywords = ", ".join(keywords)
                else:
                    keywords = []

                # ── Step 3: Similarity ───────────────────────────────────────
                search_results = svc.mock_internet_search(keywords)
                similarity = svc.calculate_similarity(summary_text, search_results)
                reg.idea_similarity_score = round(similarity * 100, 2)
                reg.idea_status = svc.get_idea_status(similarity)

                # ── Step 4: Patent ───────────────────────────────────────────
                if reg.patent_number:
                    res_pt = svc.verify_patent(
                        reg.patent_number,
                        reg.startup_name or reg.company_name
                    )
                    reg.patent_verified = res_pt.get('verified', False)
                    reg.patent_status = res_pt.get('status', 'Not Provided')
                else:
                    reg.patent_status = 'Not Submitted'
                    reg.patent_verified = False

                # ── Step 5: Scores & Final Status ────────────────────────────
                reg.idea_authenticity_score = svc.calculate_authenticity_score(
                    reg.idea_status, reg.patent_verified
                )
                status_label, rec_action = svc.get_project_verification_status(
                    reg.idea_authenticity_score, reg.idea_status, reg.patent_status
                )
                reg.project_verification_status = status_label
                reg.recommended_action = rec_action
                reg.verification_completed = True
                reg.trust_score = reg.idea_authenticity_score

                reg.save()
                ok += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [{reg.registration_number}] {reg.startup_name or reg.company_name} → "
                        f"Patent: {reg.patent_status} | Idea: {reg.idea_status} | "
                        f"Score: {reg.idea_authenticity_score} | Status: {reg.project_verification_status}"
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  [{reg.pk}] FAILED: {e}")
                )

        self.stdout.write(self.style.SUCCESS(f"\nDone. {ok}/{total} records updated."))
