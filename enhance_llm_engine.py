import os
import sys
import django
import time

# Setup django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_setup.settings')
django.setup()

from project_review.models import Registration
from project_review.services.verification import train_verification_model, KNOWLEDGE_BASE_PATH

def main():
    print("=" * 60)
    print("  MYWORLD LLM ENGINE ENHANCEMENT UTILITY")
    print("  Mode: Multi-Angle Knowledge Training")
    print("=" * 60)

    # 1. Collect Corpus
    print("\n[Step 1/3] Collecting existing startup corpus...")
    registrations = Registration.objects.exclude(profile_text="")
    corpus = [reg.profile_text for reg in registrations]
    
    if not corpus:
        print("! No startup data found in database. Enhancement aborted.")
        return
    
    print(f"  Found {len(corpus)} startup summaries for training.")

    # 2. Run Training
    print("\n[Step 2/3] Initiating Multi-Angle In-Situ Training...")
    start_time = time.time()
    result = train_verification_model(corpus)
    duration = time.time() - start_time

    if result.get('success'):
        print(f"  [OK] Success: {result.get('message')}")
        print(f"  Training took {duration:.2f}s")
        metrics = result.get('metrics', {})
        for k, v in metrics.items():
            print(f"  - {k.replace('_', ' ').title()}: {v}")
    else:
        print(f"  [Error] Failed: {result.get('message')}")

    # 3. Verify Knowledge Base
    print("\n[Step 3/3] Finalizing Knowledge Base...")
    if os.path.exists(KNOWLEDGE_BASE_PATH):
        import json
        with open(KNOWLEDGE_BASE_PATH, 'r') as f:
            kb = json.load(f)
            print(f"  Active Knowledge Base Size: {len(kb)} vectors")
            print("  Top 3 Training Anchors:")
            for ex in kb[:3]:
                print(f"    - Idea: {ex['idea'][:50]}... ({ex['similarity_score']}/10)")
    
    print("\n" + "=" * 60)
    print("  ENGINE UPGRADED TO MULTI-ANGLE ANALYSIS MODE")
    print("=" * 60)

if __name__ == "__main__":
    main()
