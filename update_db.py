
import os
import django

# Set up Django environment
import sys
sys.path.append(r'c:\Users\krithish.B.R\Desktop\final project\myworld\final_year_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_year_project.settings')
django.setup()

from project_review.models import Registration
from project_review.services import verification

def run_update():
    regs = Registration.objects.all()
    print(f"Updating {regs.count()} registrations...")
    for reg in regs:
        if reg.idea_similarity_score > 0:
            # Re-calculate status based on new rules
            old_status = reg.idea_status
            new_status = verification.get_idea_status(reg.idea_similarity_score)
            
            # Re-calculate authenticity score
            old_score = reg.idea_authenticity_score
            new_score = verification.calculate_authenticity_score(
                new_status, reg.patent_verified, reg.patent_status, float(reg.idea_similarity_score)
            )
            
            # Re-calculate project status label
            status_label, rec_action = verification.get_project_verification_status(
                new_score, new_status, reg.patent_status
            )
            
            reg.idea_status = new_status
            reg.idea_authenticity_score = new_score
            reg.project_verification_status = status_label
            reg.trust_score = new_score
            reg.save()
            print(f"Reg {reg.registration_number}: {old_status}->{new_status}, Score {old_score}->{new_score}")

if __name__ == "__main__":
    run_update()
