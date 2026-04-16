import threading
from django.utils import timezone
from .models import Company, Registration
from .services import verification as verify_service
import logging

logger = logging.getLogger(__name__)

def run_investor_verification(company_id):
    """
    Asynchronous task for investor profile verification.
    Runs LinkedIn, website, and GST verification.
    Updates trust score and verification status.
    """
    try:
        from .models import Company
        company = Company.objects.get(pk=company_id)
        logger.info(f"Starting background verification for Investor Company: {company.name} (PK:{company.id})")
        
        # 1. LinkedIn Verification
        if company.linkedin_profile:
            res_li = verify_service.verify_linkedin(company.linkedin_profile)
            company.linkedin_verified = res_li.get('verified', False)
            company.linkedin_last_checked = timezone.now()
            logger.info(f"LinkedIn check for {company.name}: {res_li.get('status')}")
            
        # 2. Website Verification
        if company.website:
            res_ws = verify_service.verify_website(company.website)
            company.website_verified = res_ws.get('verified', False)
            company.website_status = res_ws.get('status', 'Unknown')
            logger.info(f"Website check for {company.name}: {res_ws.get('status')}")
            
        # 3. GST Verification (from invoice OCR)
        if company.gst_invoice:
            res_gst = verify_service.verify_gstin(company.gst_invoice, gstin_override=company.gstin_number)
            company.gst_verified = res_gst.get('verified', False)
            company.gstin_number = res_gst.get('gstin', '')
            company.gst_extracted_from_invoice = res_gst.get('extracted', False)
            company.gst_verification_status = res_gst.get('status', 'Not Uploaded')
            
            # Save extra metadata if present
            gst_data = res_gst.get('data', {})
            if gst_data:
                company.gst_legal_name = gst_data.get('legal_name', '')
                company.gst_registration_date = gst_data.get('registration_date', '')
                company.gst_center_state = gst_data.get('state_code', '')
                company.gst_taxpayer_type = gst_data.get('taxpayer_type', '')

            logger.info(f"GST check for {company.name}: {res_gst.get('status')} (GSTIN: {company.gstin_number})")
        else:
            company.gst_verification_status = 'Not Uploaded'
            company.gst_verified = False

        # 4. Calculate Final Trust Score and Status
        company.trust_score = verify_service.calculate_investor_trust_score(company)
        company.verification_status = verify_service.get_verification_status_label(company.trust_score)
        
        company.save()
        logger.info(f"Verification complete for {company.name}. Final Trust Score: {company.trust_score}")
        
    except Exception as e:
        logger.exception(f"Unexpected error in run_investor_verification for company {company_id}: {e}")

def run_startup_verification(registration_id):
    """
    Asynchronous task for startup project verification.
    Includes Idea Analysis (extraction, keywords, search, similarity)
    and Enhanced Patent Verification.
    """
    try:
        from .models import Registration
        reg = Registration.objects.get(pk=registration_id)
        logger.info(f"Starting comprehensive verification for Startup Registration: {reg.registration_number}")
        
        # --- Step 1: Idea Summary Extraction ---
        summary_text = reg.profile_text or ""
        if reg.startup_idea_report:
            extracted = verify_service._extract_text_from_pdf(reg.startup_idea_report.path)
            if extracted:
                summary_text = extracted
                reg.extracted_summary_text = extracted
        
        # --- Step 2: Keyword Generation ---
        keywords = verify_service.generate_keywords(summary_text)
        reg.generated_keywords = ", ".join(keywords)
        
        # --- Step 3: Internet Search & Similarity ---
        search_results = verify_service.mock_internet_search(keywords)
        similarity = verify_service.calculate_similarity(summary_text, search_results)
        reg.idea_similarity_score = similarity
        reg.idea_status = verify_service.get_idea_status(similarity)
        
        # --- Step 4: Patent Verification ---
        p_num = reg.patent_number
        if not p_num and reg.patent_file:
            # Attempt extraction from document if field is empty
            p_num = verify_service.extract_patent_from_file(reg.patent_file)
            if p_num:
                reg.patent_number = p_num # Persist extracted number
                reg.recommended_action = reg.recommended_action or ""
                reg.recommended_action += " [Automated Extraction: Patent application number identified from document.]"

        if p_num:
            res_pt = verify_service.verify_patent(p_num, reg.startup_name or reg.company_name)
            reg.patent_verified = res_pt.get('verified', False)
            reg.patent_status = res_pt.get('status', 'Not Provided')
            reg.patent_owner = res_pt.get('owner', 'Unknown')
            reg.patent_detailed_status = res_pt.get('legal_status', 'Pending')
            reg.patent_registry = res_pt.get('office', 'Global Registry')
        else:
            reg.patent_verified = False
            reg.patent_status = 'Not Submitted'
            rec_msg = "A patent filing service is highly recommended to protect your IP."
            reg.recommended_action = (reg.recommended_action + "\n" + rec_msg) if reg.recommended_action else rec_msg

        # --- Step 5: Authenticity Score & Final Status ---
        reg.idea_authenticity_score = verify_service.calculate_authenticity_score(
            reg.idea_status, reg.patent_verified, reg.patent_status, float(reg.idea_similarity_score or 0.0)
        )
        
        status_label, rec_action = verify_service.get_project_verification_status(
            reg.idea_authenticity_score, reg.idea_status, reg.patent_status
        )
        reg.project_verification_status = status_label
        reg.recommended_action = rec_action
        reg.verification_completed = True
        
        # Final Trust Score (can be overall profile score)
        reg.trust_score = reg.idea_authenticity_score
        
        reg.save()
        logger.info(f"Comprehensive verification complete for startup {reg.registration_number}. Score: {reg.trust_score}")
        
        # --- Step 6: Notify Startup ---
        try:
            # 1. Internal Portal Message (if user linked)
            if reg.user:
                from .models import PortalMessage
                PortalMessage.objects.create(
                    recipient=reg.user,
                    sender_name="Verification System",
                    registration=reg,
                    text=f"Verification complete for '{reg.startup_name or reg.company_name}'. Authenticity Score: {reg.idea_authenticity_score}%. Status: {reg.project_verification_status}."
                )
            
            # 2. Email Notification
            if reg.email:
                from django.core.mail import send_mail
                from django.conf import settings
                subject = f"Verification Update: {reg.startup_name or reg.company_name}"
                message = (
                    f"Hello,\n\n"
                    f"The verification process for your startup project '{reg.startup_name or reg.company_name}' is complete.\n\n"
                    f"Authenticity Score: {reg.idea_authenticity_score}/100\n"
                    f"Status: {reg.project_verification_status}\n\n"
                    f"You can view your detailed report in the Personal Portal using your Registration ID: {reg.registration_number}\n\n"
                    f"Recommended Action:\n{reg.recommended_action}\n\n"
                    f"Best regards,\nConstructor Verification Team"
                )
                # Note: We use fail_silently=True to avoid crashing the task if email fails
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [reg.email], fail_silently=True)
                
        except Exception as notify_err:
            logger.warning(f"Failed to send startup notifications for {reg.registration_number}: {notify_err}")
            
    except Registration.DoesNotExist:
        logger.error(f"Verification Task Error: Registration with PK {registration_id} does not exist.")
    except Exception as e:
        logger.exception(f"Unexpected error in run_startup_verification for registration {registration_id}: {e}")

def run_startup_profile_verification(profile_id):
    """
    Asynchronous task for startup UserProfile verification (patent).
    """
    from .models import UserProfile
    try:
        profile = UserProfile.objects.get(pk=profile_id)
        logger.info(f"Starting background verification for UserProfile: {profile.user.username}")
        
        # 1. Patent Verification
        if profile.patent_number:
            res_pt = verify_service.verify_patent(profile.patent_number)
            profile.patent_verified = res_pt.get('verified', False)
            profile.patent_status = res_pt.get('status', 'Not Provided')
            logger.info(f"Patent check for user {profile.user.username}: {res_pt.get('status')}")
        else:
            profile.patent_status = 'Not Provided'
            profile.patent_verified = False

        # 2. Calculate Trust Score
        # Simple for now: +20 for patent
        profile.trust_score = 20 if profile.patent_verified else 0
        
        profile.save()
        logger.info(f"Verification complete for profile {profile.user.username}. Trust Score: {profile.trust_score}")
        
    except UserProfile.DoesNotExist:
        logger.error(f"Verification Task Error: UserProfile with PK {profile_id} does not exist.")
    except Exception as e:
        logger.exception(f"Unexpected error in run_startup_profile_verification for profile {profile_id}: {e}")
