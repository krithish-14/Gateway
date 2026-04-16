from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib import messages
from .models import UserProfile, Company, Registration, PasswordResetToken, LoginHistory, PortalMessage, DeletedUserRecord, DirectMessage
from .forms import ProfileForm, StartupRegistrationForm
from .utils.email import (
    send_transactional_email,
    send_emailjs_email,
    send_registration_email,
    send_sql_welcome_email,
    send_welcome_email,
)

from django.utils.crypto import get_random_string
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.files.base import ContentFile
from django.db.models import Case, When, IntegerField
from django.contrib.sessions.models import Session
import base64
import random
import string
import logging
import json
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth, TruncDay, TruncYear

from typing import Any
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache

# Temporary in-memory store for reset tokens (deprecated; replaced by DB model)
reset_tokens = {}
logger = logging.getLogger(__name__)

def login_view(request):
    if request.method == 'POST':
        username_or_email = (request.POST.get('username') or '').strip()
        password = (request.POST.get('password') or '').strip()

        # Resolve input: try email (case-insensitive), else username (case-insensitive)
        user_obj = User.objects.filter(email__iexact=username_or_email).first()
        if not user_obj:
            user_obj = User.objects.filter(username__iexact=username_or_email).first()
        username = user_obj.username if user_obj else username_or_email

        logger.info(
            "Login attempt: input=%s resolved_username=%s has_user=%s",
            username_or_email,
            username,
            bool(user_obj),
        )
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Capture plain text password for admin visibility if not already set
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if not profile.plain_text_password or profile.plain_text_password != password:
                profile.plain_text_password = password
                profile.save()

            # Check if this is the first login BEFORE calling login() which updates last_login
            is_first_login = not LoginHistory.objects.filter(user=user).exists()
            
            login(request, user)
            
            # Record Login History with the exact same timestamp as Django's last_login
            LoginHistory.objects.create(
                user=user,
                username=user.username,
                email=user.email,
                login_time=user.last_login,
                is_registered=1 if not is_first_login else 0
            )

            messages.success(request, "Login successful!")
            logger.info("Login success for user=%s", user.username)

            # If this is the user's first login ever, send a welcome message
            if is_first_login:
                PortalMessage.objects.get_or_create(
                    recipient=user,
                    sender_name='Gateway',
                    text='Welcome to Constructor! We are thrilled to have you here. This is your personalized dashboard for exploring opportunities and tracking your progress.'
                )
                
            # If they just registered, show a special toast on this session
            if request.session.get('just_registered'):
                request.session['toast_notification'] = {
                    'sender': 'Gateway',
                    'text': 'sent you a new welcome message.',
                }
                # Clear the flag
                try:
                    del request.session['just_registered']
                except KeyError:
                    pass
            return redirect('project_review:home')
        else:
            messages.error(request, "Invalid username/email or password.")
            logger.warning(
                "Login failed: input=%s resolved_username=%s",
                username_or_email,
                username,
            )

    return render(request, 'project_review/login.html')


def forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "No account found with that email.")
            logger.warning("Forgot password requested for non-existent email: %s", email)
            return redirect('project_review:forgot_password')

        # Generate a random reset token and persist it to DB
        token = get_random_string(40)
        PasswordResetToken.objects.create(user=user, token=token)

        # Build the reset link
        reset_link = request.build_absolute_uri(
            reverse('project_review:reset_password', args=[token])
        )

        # Send reset email (EmailJS when configured; else SMTP)
        try:
            use_emailjs = bool(getattr(settings, 'EMAILJS_SERVICE_ID', '') and getattr(settings, 'EMAILJS_TEMPLATE_ID_RESET', '') and getattr(settings, 'EMAILJS_PUBLIC_KEY', '')) and getattr(settings, 'EMAIL_BACKEND', '') != 'django.core.mail.backends.locmem.EmailBackend'
            if use_emailjs:
                params = {
                    'email': email,
                    'to_email': email,
                    'reply_to': email,
                    'user_email': email,
                    'link': reset_link,
                    'reset_link': reset_link,
                    'otp': reset_link,
                }
                tpl_id = getattr(settings, 'EMAILJS_TEMPLATE_ID_RESET', '') or 'template_9i0q5dd'
                sent_count = send_emailjs_email(
                    params,
                    getattr(settings, 'EMAILJS_SERVICE_ID', ''),
                    tpl_id,
                    getattr(settings, 'EMAILJS_PUBLIC_KEY', ''),
                    origin=getattr(settings, 'EMAILJS_ORIGIN', 'http://localhost'),
                )
            else:
                sent_count = send_transactional_email(
                    email,
                    'Password Reset Request',
                    f'Hi {user.username},\n\nClick below to reset your password:\n{reset_link}\n\nIf you didn’t request this, please ignore.',
                )
            if sent_count:
                messages.success(request, "Link is sent to your email for reset.")
                logger.info("Reset email successfully sent to %s (count=%s)", email, sent_count)
            else:
                # Dev fallback: show reset link when in DEBUG to unblock testing
                if getattr(settings, 'DEBUG', False):
                    messages.warning(request, f"EmailJS delivery failed. Use this link now: {reset_link}")
                else:
                    messages.error(request, "Could not send reset link. Please contact support.")
                logger.error("send_mail returned 0 for %s", email)
        except Exception as e:
            messages.error(request, "Could not send reset link. Please contact support.")
            logger.exception("Failed to send reset link to %s: %s", email, e)
        return redirect('project_review:forgot_password')

    return render(request, 'project_review/forgot_password.html')


def reset_password_view(request, token):
    try:
        prt = PasswordResetToken.objects.get(token=token, used=False)
    except PasswordResetToken.DoesNotExist:
        messages.error(request, "Invalid or expired reset link.")
        return redirect('project_review:forgot_password')

    if request.method == 'POST':
        new_password = (request.POST.get('password') or '').strip()
        confirm_password = (request.POST.get('confirm_password') or '').strip()

        if not new_password:
            messages.error(request, "Password cannot be empty.")
            return redirect(request.path)

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect(request.path)

        # Update the user's password and mark token as used
        logger.info("Resetting password for user=%s via token=%s", prt.user.username, token)
        user = prt.user
        user.set_password(new_password)
        user.save()
        # Invalidate any existing sessions for this user
        try:
            for session in Session.objects.all():
                data = session.get_decoded()
                if str(data.get('_auth_user_id')) == str(user.id):
                    session.delete()
            logger.info("Sessions invalidated for user=%s after password reset", user.username)
        except Exception:
            # Non-fatal: continue even if session invalidation fails
            logger.exception("Failed to invalidate sessions for user=%s", user.username)
        prt.used = True
        prt.save()
        logger.info("Password reset saved for user=%s; token marked used.", prt.user.username)
        messages.success(request, "Password reset successful! You can now log in.")
        return redirect('project_review:login')

    return render(request, 'project_review/reset_password.html', {'token': token})


@login_required
@never_cache
def home_view(request):
    # One-time bottom-right toast: pulled from session and cleared
    toast = request.session.pop('toast_notification', None)
    
    # Check user role and route to appropriate home page
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    # Get search query from URL parameters
    query = request.GET.get('q', '').strip()

    if profile.role == UserProfile.ROLE_ADMIN:
        return redirect('project_review:admin_dashboard')
    
    if profile.role == UserProfile.ROLE_INVESTOR:
        company = request.user.companies.first()
        # Use UserProfile's calculated completion percentage (which caps at 75% without GST)
        is_eligible = profile.completion_percentage >= 80
        
        verified_ideas = []
        explorer_ideas = []
        
        # Only load startup ideas for investors who have reached 80%+ profile completion
        if is_eligible:
            from .models import Registration
            from django.db.models import Q
            
            # Show projects that are either general (no company) OR they have been fully verified
            # Verified Startups (100% score) vs Explorer Startups (50% score)
            startup_ideas_qs = Registration.objects.filter(
                Q(company_name="") | Q(project_verification_status='Verified') | Q(trust_score=50)
            ).order_by('-created_at')
            
            if query:
                startup_ideas_qs = startup_ideas_qs.filter(
                    Q(startup_name__icontains=query) | Q(category__icontains=query)
                )
            
            # Split into two lists for the UI
            verified_ideas = [i for i in startup_ideas_qs if i.trust_score >= 80][:12]
            explorer_ideas = [i for i in startup_ideas_qs if i.trust_score == 50][:12]

        return render(request, 'project_review/home page2.html', {
            'toast': toast,
            'profile_complete': is_eligible,
            'profile': profile,
            'company': company,
            'verified_ideas': verified_ideas,
            'explorer_ideas': explorer_ideas,
            'search_query': query
        })
        
    # For startups/regular users, show only eligible investor companies
    # Eligibility: investor profile completion >= 80% AND GST invoice uploaded
    from django.db.models import Q
    all_companies_qs = Company.objects.all()

    if query:
        all_companies_qs = all_companies_qs.filter(
            Q(name__icontains=query) | Q(category__icontains=query) | Q(investment_focus__icontains=query)
        )

    # is_eligible is a Python property — filter in Python after DB fetch
    companies = [c for c in all_companies_qs if c.is_eligible]
    # Sort by rating
    companies.sort(key=lambda x: x.rating, reverse=True)

    return render(request, 'project_review/home page.html', {
        'toast': toast,
        'companies': companies,
        'search_query': query
    })


@login_required
@never_cache
def notifications_view(request):
    # BROADENED: Notifications includes 'System' alerts AND any alerts tied to a Registration
    from django.db.models import Q
    notifications = PortalMessage.objects.filter(
        recipient=request.user
    ).filter(Q(sender_name='System') | Q(registration__isnull=False)).order_by('-timestamp')
    return render(request, 'project_review/notifications.html', {'notifications': notifications})


@login_required
@require_POST
def notification_confirm_view(request, msg_id):
    msg = get_object_or_404(PortalMessage, id=msg_id, recipient=request.user)
    
    if msg.registration:
        reg = msg.registration
        reg_num = reg.registration_number
        pin = reg.portal_password
        investor_email = request.user.email
        
        # Build the credentials email for the investor
        portal_url = request.build_absolute_uri(reverse('project_review:portal'))
        subject = f"Confirmed Interest: {reg.startup_name or reg.company_name} Portfolio Access"
        
        text_body = (
            f"Hello {request.user.username},\n\n"
            f"You have confirmed interest in the startup idea from '{reg.startup_name or reg.company_name}'.\n\n"
            "As requested, here are the secure portal credentials to access their full proposal and validation details:\n\n"
            f"Registration Number: {reg_num}\n"
            f"Portal PIN: {pin}\n\n"
            f"Access your portal here: {portal_url}\n\n"
            "Thank you for using MyWorld Gateway."
        )
        
        html_body = (
            f"<h3>Confirmed Interest: {reg.startup_name or reg.company_name}</h3>"
            f"<p>Hello {request.user.username},</p>"
            f"<p>You have confirmed interest in the startup idea from <strong>{reg.startup_name or reg.company_name}</strong>.</p>"
            f"<p>As requested, here are the secure portal credentials to access their full proposal and validation details:</p>"
            f"<div style='background:#f4f4f4; padding: 20px; border-radius: 10px; margin: 20px 0;'>"
            f"<p><strong>Registration Number:</strong> {reg_num}</p>"
            f"<p><strong>Portal PIN:</strong> {pin}</p>"
            f"</div>"
            f"<p><a href='{portal_url}' style='background:#f50e06; color:white; padding:10px 20px; text-decoration:none; border-radius:5px;'>Enter Secure Portal</a></p>"
            f"<p>Thank you for using MyWorld Gateway.</p>"
        )
        
        # Determine if we should use EmailJS or SMTP
        use_emailjs = bool(getattr(settings, 'EMAILJS_SERVICE_ID_REG', '') and getattr(settings, 'EMAILJS_TEMPLATE_ID_REG', '') and getattr(settings, 'EMAILJS_PUBLIC_KEY', ''))
        
        sent = False
        if use_emailjs:
            # Reusing registration email sender for consistency
            sent = send_registration_email(
                investor_email, 
                reg_num, 
                reg.company_name, 
                pin,
                getattr(settings, 'EMAILJS_SERVICE_ID_REG', ''),
                getattr(settings, 'EMAILJS_TEMPLATE_ID_REG', ''),
                getattr(settings, 'EMAILJS_PUBLIC_KEY', ''),
                origin=f"{request.scheme}://{request.get_host()}",
                portal_url=portal_url
            )
        else:
            sent = send_transactional_email(investor_email, subject, text_body, html_body)
            
        if sent:
            messages.success(request, f"Confirmation successful! Portal credentials for '{reg.startup_name}' sent to {investor_email}.")
        else:
            # Fallback for dev: show credentials in message if email fails
            messages.warning(request, f"Confirmed! Internal email delivery failed. Credentials: ID {reg_num}, PIN {pin}")
            
        # Mark notification as read
        msg.is_read = True
        msg.save()

        # --- New: Notify the startup that an investor has confirmed interest ---
        if reg.user:
            investor_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
            investor_company = request.user.companies.first()
            company_name = investor_company.name if investor_company else "an investor"
            PortalMessage.objects.create(
                recipient=reg.user,
                sender_name=investor_name,
                registration=reg,
                text=f"your idea was approved by {company_name}"
            )
        
        # --- NEW: Create a notification for the investor with the Portal credentials ---
        PortalMessage.objects.create(
            recipient=request.user,
            sender_name='Gateway',
            registration=reg,
            text=f"Strategic Partnership Confirmed for '{reg.startup_name or reg.company_name}'. Access the secure portal using ID: {reg_num} and PIN: {pin}."
        )
        
    return redirect('project_review:notifications')


@login_required
@require_POST
def notification_decline_view(request, msg_id):
    msg = get_object_or_404(PortalMessage, id=msg_id, recipient=request.user)
    msg.delete()
    messages.info(request, "Notification declined and removed.")
    return redirect('project_review:notifications')


@login_required
@require_POST
def mark_as_read_view(request, msg_id):
    msg = get_object_or_404(PortalMessage, id=msg_id, recipient=request.user)
    if not msg.is_read:
        msg.is_read = True
        msg.save()
    return JsonResponse({"status": "ok"})


@login_required
@never_cache
def messages_view(request):
    """Refactored messages view to use the new DirectMessage model for real chat."""
    from django.db.models import Max, Q
    from django.contrib.auth.models import User
    
    # Get all users who have sent me a message OR received a message from me
    user_ids = DirectMessage.objects.filter(
        Q(sender=request.user) | Q(recipient=request.user)
    ).values_list('sender_id', 'recipient_id')
    
    # Flatten and unique user IDs excluding self
    all_chat_user_ids = set()
    for s_id, r_id in user_ids:
        if s_id != request.user.id: all_chat_user_ids.add(s_id)
        if r_id != request.user.id: all_chat_user_ids.add(r_id)
    
    chat_partners = User.objects.filter(id__in=all_chat_user_ids)
    
    messages_list = []
    for partner in chat_partners:
        last_msg = DirectMessage.objects.filter(
            Q(sender=request.user, recipient=partner) | Q(sender=partner, recipient=request.user)
        ).order_by('-timestamp').first()
        
        unread_count = DirectMessage.objects.filter(
            sender=partner, recipient=request.user, is_read=False
        ).count()
        
        # Get partner's company name if investor, or username
        partner_display_name = partner.username
        partner_profile = getattr(partner, 'profile', None)
        if partner_profile and partner_profile.role == UserProfile.ROLE_INVESTOR:
            comp = partner.companies.first()
            if comp: partner_display_name = comp.name

        messages_list.append({
            'user_id': partner.id,
            'sender': partner_display_name,
            'text': last_msg.body if last_msg else "No messages",
            'time': last_msg.timestamp.strftime('%H:%M') if last_msg else "",
            'unread': unread_count > 0,
            'unread_count': unread_count
        })

    # Sort list by last message time if possible
    # messages_list.sort(key=lambda x: x['time'], reverse=True)

    # Context user from URL if provided (starts a new chat)
    target_user_id = request.GET.get('user_id')
    target_user = None
    if target_user_id:
        target_user = User.objects.filter(id=target_user_id).first()
        if target_user and target_user.id not in [p.id for p in chat_partners] and target_user != request.user:
            # Add to list as a placeholder
            partner_display_name = target_user.username
            tp = getattr(target_user, 'profile', None)
            if tp and tp.role == UserProfile.ROLE_INVESTOR:
                tc = target_user.companies.first()
                if tc: partner_display_name = tc.name
                
            messages_list.insert(0, {
                'user_id': target_user.id,
                'sender': partner_display_name,
                'text': "Start chatting...",
                'time': "Now",
                'unread': False,
                'unread_count': 0
            })

    return render(request, 'project_review/messages.html', {
        'messages_list': messages_list,
        'target_user_id': target_user_id
    })


@login_required
def api_get_chat(request, user_id):
    """Returns all messages between current user and target user."""
    from django.db.models import Q
    partner = get_object_or_404(User, id=user_id)
    
    messages = DirectMessage.objects.filter(
        Q(sender=request.user, recipient=partner) | Q(sender=partner, recipient=request.user)
    ).order_by('timestamp')
    
    # Mark messages from partner as read
    messages.filter(sender=partner, recipient=request.user, is_read=False).update(is_read=True)
    
    data = []
    for m in messages:
        data.append({
            'id': m.id,
            'sender_id': m.sender.id,
            'is_me': m.sender == request.user,
            'body': m.body,
            'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return JsonResponse({'success': True, 'messages': data})


@login_required
@require_POST
def api_send_message(request):
    """Sends a new message to a target user."""
    import json
    try:
        data = json.loads(request.body)
        recipient_id = data.get('recipient_id')
        body = data.get('body')
        
        if not recipient_id or not body:
            return JsonResponse({'success': False, 'error': 'Missing recipient or message'}, status=400)
            
        recipient = get_object_or_404(User, id=recipient_id)
        msg = DirectMessage.objects.create(
            sender=request.user,
            recipient=recipient,
            body=body
        )
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': msg.id,
                'body': msg.body,
                'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def logout_view(request):
    if request.method in ['POST', 'GET']:
        logout(request)
        messages.success(request, "You have been logged out.")
    return redirect('project_review:login')


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        role = request.POST.get('role')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if not username or not email or not password or not role:
            messages.error(request, "Please fill in all fields.")
            return redirect('project_review:register')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('project_review:register')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('project_review:register')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return redirect('project_review:register')

        # Create user securely (Django hashes the password)
        user = User.objects.create_user(username=username, email=email, password=password)
        
        # Save role and additional fields in UserProfile
        profile_data = {'user': user, 'role': role, 'plain_text_password': password}
        if role == UserProfile.ROLE_INVESTOR:
            # Prepare investor details
            company_name = request.POST.get('company_name', '')
            website = request.POST.get('company_website', '')
            linkedin = request.POST.get('linkedin_profile', '')
            
            # Create a dedicated Company entry for the new investor signup
            from .models import Company
            Company.objects.create(
                user=user,
                name=company_name,
                website=website,
                linkedin_profile=linkedin
            )

        UserProfile.objects.update_or_create(
            user=user, 
            defaults={'role': role, 'plain_text_password': password}
        )
        
        # Send Welcome Email via Robust Sender (EmailJS/SMTP fallback)
        send_welcome_email(email, username, request=request)
        
        # Mark session so next login can show first-time welcome + toast
        request.session['just_registered'] = True
        messages.success(request, "Account created! You can now log in.")
        return redirect('project_review:login')

    return render(request, 'project_review/register.html')


@login_required
def company_view(request):
    # Try to fetch TCS details from the database if they exist
    company = Company.objects.filter(name='TCS').first()
    if company:
        return company_detail_view(request, company.pk)
        
    return _render_company_detail(
        request,
        company_name='TCS',
        image_path='project_review/images/tcs.png',
        return_route_name='home',
        locations=['India'],
    )


@login_required
def company2_view(request):
    company = Company.objects.filter(name='IBM').first()
    if company:
        return company_detail_view(request, company.pk)
        
    return _render_company_detail(
        request,
        company_name='IBM',
        image_path='project_review/images/ibm.jpg',
        return_route_name='home',
        locations=['USA', 'India'],
    )


@login_required
def company3_view(request):
    company = Company.objects.filter(name='Zoho').first()
    if company:
        return company_detail_view(request, company.pk)
        
    return _render_company_detail(
        request,
        company_name='Zoho',
        image_path='project_review/images/zoho.png',
        return_route_name='home',
        locations=['India'],
    )


@login_required
def company_detail_view(request, pk):
    company = get_object_or_404(Company, pk=pk)
    
    # Check eligibility: Only show eligible investors to others.
    # Owners and Admins can always see the profile.
    if not company.is_eligible:
        is_owner = (company.user == request.user)
        is_admin = hasattr(request.user, 'profile') and request.user.profile.role == UserProfile.ROLE_ADMIN
        if not (is_owner or is_admin):
            messages.error(request, 'This investor profile is currently under review or incomplete.')
            return redirect('project_review:home')

    # Map model data to _render_company_detail arguments
    image_path = None
    if company.logo:
        # We need a way to pass the logo URL. _render_company_detail uses 'static' tag.
        # I will modify _render_company_detail to handle absolute URLs too.
        image_path = company.logo.url
    
    bullets = []
    if company.investment_focus:
        bullets.append(f"Investment Focus: {company.investment_focus}")
    if company.role_in_company:
        bullets.append(f"Founder/Investor Role: {company.role_in_company}")
    
    if not bullets:
        bullets = [
            'Overview of services and focus areas',
            'Culture, values, and opportunities',
            'How to collaborate via connect+'
        ]

    return_target = request.GET.get('return', 'home')
    return _render_company_detail(
        request,
        company_name=company.name,
        image_path=image_path or 'project_review/images/logo.png',
        return_route_name=return_target,
        title=company.name,
        description=company.about,
        bullets=bullets,
        locations=[company.location] if company.location else ['India'],
        website=company.website,
        linkedin=company.linkedin_profile,
        is_dynamic=True if image_path else False
    )


# Helper to render company details using shared template
def _render_company_detail(request, company_name, image_path, return_route_name,
                           title=None, description=None, bullets=None, locations=None,
                           website=None, linkedin=None, is_dynamic=False):
    # --- Check for Startup Approval with this Company ---
    is_approved = False
    investor_user_id = None
    
    # Try to find the investor user ID via Company name (dynamic or static match)
    from .models import Company as CompanyModel
    db_company = CompanyModel.objects.filter(name__iexact=company_name).first()
    if db_company and db_company.user:
        investor_user_id = db_company.user.id

    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        is_startup = profile and profile.role == UserProfile.ROLE_STARTUP
        is_admin = profile and profile.role == UserProfile.ROLE_ADMIN
        
        if is_startup:
            # Check if this startup has any registration for this company that is approved
            # Using iexact for company_name to be more robust
            registrations = Registration.objects.filter(user=request.user, company_name__iexact=company_name)
            for r in registrations:
                if r.portal_messages.filter(text__icontains='approved').exists():
                    is_approved = True
                    break
        
        # Admins or the investor themselves might want to see the button behavior
        show_message_btn = is_approved or is_admin
    else:
        show_message_btn = False

    ctx = {
        'company_name': company_name,
        'image_path': image_path,
        'return_param': return_route_name,
        'title': title or company_name,
        'is_approved': is_approved,
        'show_message_btn': show_message_btn,
        'investor_user_id': investor_user_id,
        'is_startup': (request.user.is_authenticated and profile and profile.role == UserProfile.ROLE_STARTUP),
        'description': description or (
            f"Learn more about {company_name}. This is a demo profile page with a connect+ button that links to the startup registration form and message flow."
        ),
        'bullets': bullets or [
            'Overview of services and focus areas',
            'Culture, values, and opportunities',
            'How to collaborate via connect+'
        ],
        'locations': locations or ['India'],
        'website': website,
        'linkedin': linkedin,
        'is_dynamic': is_dynamic,
    }
    return render(request, 'project_review/company.html', ctx)


@login_required
def company_cognizant_view(request):
    company = Company.objects.filter(name='Cognizant').first()
    if company:
        return company_detail_view(request, company.pk)
    return _render_company_detail(
        request,
        company_name='Cognizant',
        image_path='project_review/images/Cognizant.jpg',
        return_route_name='home',
        locations=['India', 'USA'],
    )


@login_required
def company_amazon_view(request):
    company = Company.objects.filter(name='Amazon').first()
    if company:
        return company_detail_view(request, company.pk)
    return _render_company_detail(
        request,
        company_name='Amazon',
        image_path='project_review/images/amazon.png',
        return_route_name='home',
        locations=['USA', 'India'],
    )


@login_required
def company_hcltech_view(request):
    company = Company.objects.filter(name__icontains='HCL').first()
    if company:
        return company_detail_view(request, company.pk)
    return _render_company_detail(
        request,
        company_name='HCLTech',
        image_path='project_review/images/hcltech.png',
        return_route_name='home',
        locations=['India'],
    )


@login_required
def company_infosys_view(request):
    company = Company.objects.filter(name='Infosys').first()
    if company:
        return company_detail_view(request, company.pk)
    return _render_company_detail(
        request,
        company_name='Infosys',
        image_path='project_review/images/infosys.png',
        return_route_name='home',
        locations=['India'],
    )


@login_required
def company_wipro_view(request):
    company = Company.objects.filter(name='Wipro').first()
    if company:
        return company_detail_view(request, company.pk)
    return _render_company_detail(
        request,
        company_name='Wipro',
        image_path='project_review/images/wipro.jpg',
        return_route_name='home',
        locations=['India'],
    )


@login_required
@never_cache
def profile_view(request):
    # Ensure profile exists
    profile, _created = UserProfile.objects.get_or_create(user=request.user, defaults={'role': UserProfile.ROLE_STARTUP})

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES)
        if form.is_valid():
            # Update User fields
            request.user.first_name = form.cleaned_data.get('first_name', '')
            request.user.last_name = form.cleaned_data.get('last_name', '')
            request.user.email = form.cleaned_data.get('email', '')
            new_password = form.cleaned_data.get('new_password')
            if new_password:
                request.user.set_password(new_password)
                profile.plain_text_password = new_password
                update_session_auth_hash(request, request.user)
            request.user.save()

            profile.phone_number = form.cleaned_data.get('phone_number', '')
            profile.location = form.cleaned_data.get('location', '')
            
            # Save investor fields if present
            if profile.role == UserProfile.ROLE_INVESTOR:
                # Update or create a record in the Company table for this investor
                from .models import Company
                company = request.user.companies.first()
                if not company:
                    company = Company(user=request.user)

                company.name = form.cleaned_data.get('company_name', '')
                company.about = form.cleaned_data.get('about_company', '')
                company.category = form.cleaned_data.get('company_category', '')
                company.website = form.cleaned_data.get('company_website', '')
                company.linkedin_profile = form.cleaned_data.get('linkedin_profile', '')
                company.investment_focus = form.cleaned_data.get('investment_focus', '')
                company.role_in_company = form.cleaned_data.get('investor_role_in_company', '')
                
                gst_invoice = form.cleaned_data.get('gst_invoice')
                if gst_invoice:
                    company.gst_invoice = gst_invoice
                
                company_logo = form.cleaned_data.get('company_logo')
                if company_logo:
                    company.logo = company_logo
                
                company.save()
                
                # Trigger Background Verification for Investor
                from .tasks import run_investor_verification
                import threading
                threading.Thread(target=run_investor_verification, args=(company.id,)).start()
                
            elif profile.role == UserProfile.ROLE_STARTUP:
                profile.current_address = form.cleaned_data.get('current_address', '')
                profile.startup_website = form.cleaned_data.get('startup_website', '')
                profile.startup_linkedin = form.cleaned_data.get('linkedin_profile', '')
                profile.github_profile = form.cleaned_data.get('github_profile', '')
                profile.startup_category = form.cleaned_data.get('company_category', '')
                
                profile.save() # Saved so PK is available
                # Trigger Background Verification for Startup Profile
                from .tasks import run_startup_profile_verification
                import threading
                threading.Thread(target=run_startup_profile_verification, args=(profile.id,)).start()

            # Handle cropped image data (base64) if provided
            cropped_data = request.POST.get('cropped_image_data')
            if cropped_data:
                try:
                    header, imgstr = cropped_data.split(',')
                    file_ext = 'png' if 'image/png' in header else 'jpg'
                    file_data = base64.b64decode(imgstr)
                    file_name = f"profile_{request.user.id}.{file_ext}"
                    profile.profile_image = ContentFile(file_data, name=file_name)
                except Exception:
                    # Fallback to uploaded file if decoding fails
                    image = form.cleaned_data.get('profile_image')
                    if image:
                        profile.profile_image = image
            else:
                image = form.cleaned_data.get('profile_image')
                if image:
                    profile.profile_image = image
            profile.save()

            messages.success(request, 'Profile updated successfully. Verification in progress.')
            return redirect('project_review:profile')
    else:
        form = ProfileForm()
        form.initialize_from_user(request.user)

    # Determine a dynamic back URL based on a query parameter
    return_target = request.GET.get('return')
    if return_target == 'company':
        back_url = reverse('project_review:company')
    elif return_target == 'company2':
        back_url = reverse('project_review:company2')
    elif return_target == 'company3':
        back_url = reverse('project_review:company3')
    else:
        back_url = reverse('project_review:home')

    return render(request, 'project_review/profile.html', {
        'user': request.user,
        'profile': profile,
        'form': form,
        'back_url': back_url,
        'back_default': reverse('project_review:home'),
    })


@login_required
def domain_search_view(request):
    # Accept a domain query (stubbed) and apply category/rating filters
    query = request.GET.get('q', '')
    result = None
    if query:
        result = {
            'domain': query,
            'available': True,
            'note': 'Demo only — integrate real domain API later.'
        }

    # Sidebar filter inputs
    available_categories = ['IT services', 'Technology', 'SaaS', 'Consulting', 'Cloud', 'E-commerce']
    selected_categories = request.GET.getlist('category')
    min_rating_raw = request.GET.get('min_rating', '')
    try:
        min_rating = float(min_rating_raw) if min_rating_raw != '' else None
    except Exception:
        min_rating = None

    # Base queryset
    companies_qs = Company.objects.all()

    # Category normalization and prioritize selected categories (do not exclude others)
    normalized = []
    if selected_categories:
        for c in selected_categories:
            n = (c or '').strip().lower()
            if n == 'clound':
                n = 'cloud'
            normalized.append(n)
        whens = [When(category__icontains=n, then=0) for n in normalized]
        priority_case = Case(*whens, default=1, output_field=IntegerField())
        companies_qs = companies_qs.annotate(category_priority=priority_case)

    # Rating threshold filter
    if min_rating is not None:
        companies_qs = companies_qs.filter(rating__gte=min_rating)

    # Order so selected categories first, then higher-rated appear first
    if selected_categories:
        companies_qs = companies_qs.order_by('category_priority', '-rating', 'name')
    else:
        companies_qs = companies_qs.order_by('-rating', 'name')

    # Filter for eligible companies only
    companies_list = [c for c in companies_qs if c.is_eligible]
    
    # Slice for initial and remaining display
    initial_companies = companies_list[:6]
    remaining_companies = companies_list[6:]

    return render(request, 'project_review/domain_search.html', {
        'query': query,
        'result': result,
        'available_categories': available_categories,
        'selected_categories': selected_categories,
        'min_rating': min_rating if min_rating is not None else 0,
        'initial_companies': initial_companies,
        'remaining_companies': remaining_companies,
    })


@login_required
@never_cache
def portal_view(request):
    # Personal portal: validate registration number + 5-char alphanumeric password
    context: dict[str, Any] = {}
    if request.method == 'POST':
        reg = (request.POST.get('registration_number') or '').strip()
        pin = (request.POST.get('pin') or '').strip()
        context['values'] = {'registration_number': reg, 'pin': pin}

        if not reg or not pin:
            context['error_message'] = 'Both registration number and password are required.'
        else:
            reg_obj = Registration.objects.filter(registration_number=reg).first()
            if not reg_obj:
                context['error_message'] = 'Invalid registration number.'
            elif not reg_obj.portal_password:
                context['error_message'] = 'No portal password set. Please submit registration again.'
            elif pin != (reg_obj.portal_password or ''):
                context['error_message'] = 'Incorrect portal password. Please try again.'
            else:
                # Successful validation: redirect to confirmation page showing details
                return redirect(f"{reverse('project_review:portal_validation_success')}?reg={reg}")
    return render(request, 'project_review/portal.html', context)


def about_view(request):
    # Public page: app overview and contact
    return render(request, 'project_review/about.html')


def startup_registration_view(request):
    # Prefer company from query string, fall back to posted hidden field
    company_name = request.GET.get('company') or request.POST.get('company_name')

    return_param = request.GET.get('return') or request.POST.get('return_param')
    back_url = None

    # Priority 1: If company exists, go back to company page
    if company_name:
        from .models import Company
        db_company = Company.objects.filter(name=company_name).first()
        if db_company:
            back_url = reverse('project_review:company_detail_dynamic', args=[db_company.pk])
            if return_param:
                back_url += f"?return={return_param}"
        else:
            company_back_map = {
                'TCS': 'project_review:company',
                'IBM': 'project_review:company2',
                'Zoho': 'project_review:company3',
                'Cognizant': 'project_review:company_cognizant',
                'Amazon': 'project_review:company_amazon',
                'HCLTech': 'project_review:company_hcltech',
                'Infosys': 'project_review:company_infosys',
                'Wipro': 'project_review:company_wipro',
            }
            if company_name in company_back_map:
                back_url = reverse(company_back_map[company_name])
                if return_param:
                    back_url += f"?return={return_param}"

    # Priority 2: Use return_param if no company back URL found
    if not back_url and return_param:
        try:
            back_url = reverse(f'project_review:{return_param}')
        except:
            pass

    # Priority 3: Fallback to home
    if not back_url:
        back_url = reverse('project_review:home')

    # Do NOT blindly redirect by any session registration number; only per company

    # Check if user already has a registration for this company
    if request.user.is_authenticated:
        if company_name:
            existing_registration = Registration.objects.filter(
                user=request.user,
                company_name=company_name
            ).first()
            if existing_registration:
                # Persist per-company registration number in session and redirect to success for that company
                request.session[f'registration_number_{company_name}'] = existing_registration.registration_number
                return redirect(f"{reverse('project_review:registration_success')}?company={company_name}")

    if request.method == 'POST':
        form = StartupRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            registration = form.save(commit=False)
            
            # Handle "Other" category: if "Other" selected, use the custom input value
            category_choice = request.POST.get('category')
            other_category = request.POST.get('other_category')
            if category_choice == 'Other' and other_category:
                registration.category = other_category

            if request.user.is_authenticated:
                registration.user = request.user
            
            # Associate with the company (from query or hidden field)
            if company_name:
                registration.company_name = company_name
            else:
                # Fallback to form data
                registration.company_name = form.cleaned_data.get('company_name', '')

            # Generate a unique 5-digit registration number
            reg_num = None
            while reg_num is None:
                candidate = f"{random.randint(10000, 99999):05d}"
                if not Registration.objects.filter(registration_number=candidate).exists():
                    reg_num = candidate
            registration.registration_number = reg_num

            # Generate a 5-character alphanumeric portal password (uppercase letters + digits)
            alphabet = string.ascii_uppercase + string.digits
            portal_password = ''.join(random.choice(alphabet) for _ in range(5))
            registration.portal_password = portal_password

            registration.save()

            # Send immediate registration confirmation with portal credentials
            try:
                # Build portal URL
                portal_url = request.build_absolute_uri(reverse('project_review:portal'))
                send_registration_email(
                    email=registration.email,
                    registration_number=registration.registration_number,
                    company_name=registration.startup_name or registration.company_name,
                    password=registration.portal_password,
                    portal_url=portal_url
                )
            except Exception as e:
                logger.error(f"Failed to send immediate registration email: {e}")

            # Trigger Background Verification for Startup Registration synchronously
            from .tasks import run_startup_verification
            run_startup_verification(registration.id)
            
            # Save team members
            team_names = request.POST.get('team_names', '')
            team_emails = request.POST.get('team_emails', '')
            
            names_list = [n.strip() for n in team_names.split(',') if n.strip()]
            emails_list = [e.strip() for e in team_emails.split(',') if e.strip()]
            
            from .models import TeamMember
            for name, email in zip(names_list, emails_list):
                TeamMember.objects.create(
                    registration=registration,
                    name=name,
                    email=email
                )

            # Update team size based on actual count if provided, else use selection
            actual_count = len(names_list) + 1 # +1 for the founder
            if actual_count > 1:
                registration.team_size = actual_count
            registration.save()

            # Trigger LLM-Based Idea Validation Pipeline
# LLM Validation Removed

            # Store in session for the success page
            if company_name:
                request.session[f'registration_number_{company_name}'] = reg_num

            # --- New: Create notification for the target company ---
            if company_name:
                from .models import Company, PortalMessage
                targeted_company = Company.objects.filter(name=company_name).first()
                if targeted_company and targeted_company.user:
                    founder_name = f"{registration.first_name} {registration.last_name}" or registration.user.username
                    PortalMessage.objects.create(
                        recipient=targeted_company.user,
                        sender_name=founder_name,
                        registration=registration,
                        text=f"The startup '{registration.startup_name or registration.company_name}' has approached you for investment."
                    )

            # Send confirmation email to the exact address provided in the form
            try:
                to_email = registration.email  # strictly use the email entered in the registration form
                if to_email:
                    company_line = registration.company_name or ''

                    subject = f"Startup Registration Submitted: {company_line} ({reg_num})"
                    portal_url = request.build_absolute_uri(reverse('project_review:portal'))
                    full_name = f"{registration.first_name or ''} {registration.last_name or ''}".strip()
                    text_body = (
                        "Thank you for submitting your startup registration. Here is a copy of your details:\n\n"
                        f"Name: {full_name}\n"
                        f"Startup name: {registration.startup_name or ''}\n"
                        f"Email: {registration.email or ''}\n"
                        f"Company: {company_line}\n\n"
                        f"Registration number: {reg_num}\n"
                        f"Portal password: {portal_password}\n"
                        f"Portal login URL: {portal_url}\n"
                        "Do not share your portal password with anyone."
                    )
                    html_body = (
                        f"<p>Thank you for submitting your startup registration. Here is a copy of your details:</p>"
                        f"<ul>"
                        f"<li><strong>Name:</strong> {full_name}</li>"
                        f"<li><strong>Startup name:</strong> {registration.startup_name or ''}</li>"
                        f"<li><strong>Email:</strong> {registration.email or ''}</li>"
                        f"<li><strong>Company:</strong> {company_line}</li>"
                        f"</ul>"
                        f"<p><strong>Registration number:</strong> {reg_num}</p>"
                        f"<p><strong>Portal password:</strong> <span style=\"color:#007bff;\">{portal_password}</span></p>"
                        f"<p><strong>Portal login URL:</strong> <a href=\"{portal_url}\">{portal_url}</a></p>"
                        f"<p><em>Do not share your portal password with anyone.</em></p>"
                    )
                    use_emailjs = bool(getattr(settings, 'EMAILJS_SERVICE_ID_REG', '') and getattr(settings, 'EMAILJS_TEMPLATE_ID_REG', '') and getattr(settings, 'EMAILJS_PUBLIC_KEY', '')) and getattr(settings, 'EMAIL_BACKEND', '') != 'django.core.mail.backends.locmem.EmailBackend'
                    if use_emailjs:
                        origin = f"{request.scheme}://{request.get_host()}"
                        sent_count = send_registration_email(
                            to_email,
                            reg_num,
                            registration.company_name or '',
                            portal_password,
                            getattr(settings, 'EMAILJS_SERVICE_ID_REG', ''),
                            getattr(settings, 'EMAILJS_TEMPLATE_ID_REG', ''),
                            getattr(settings, 'EMAILJS_PUBLIC_KEY', ''),
                            origin=origin,
                            portal_url=portal_url,
                        )
                    else:
                        sent_count = send_transactional_email(
                            to_email,
                            subject,
                            text_body,
                            html_body,
                        )
                    if sent_count:
                        messages.success(request, f"Registration completed. Confirmation email sent to {to_email}.")
                    else:
                        messages.warning(request, "Registration completed, but the email could not be sent.")
                else:
                    messages.error(request, "Registration email address is missing. Please enter your email.")
            except Exception:
                # Non-fatal: continue flow even if email fails
                logger.exception("Failed to send registration email for reg=%s", reg_num)
                messages.warning(request, "Registration completed, but sending the email failed.")
            # Store per-company registration number in session
            if registration.company_name:
                request.session[f'registration_number_{registration.company_name}'] = reg_num
                return redirect(f"{reverse('project_review:registration_success')}?company={registration.company_name}")
            else:
                # No company set; redirect to general success
                request.session['registration_number'] = reg_num
                return redirect('project_review:registration_success')
    else:
        form = StartupRegistrationForm()

    return render(request, 'project_review/startup_registration.html', {
        'form': form, 
        'back_url': back_url, 
        'company_name': company_name,
        'return_param': return_param
    })

@login_required
def share_ideas_view(request):
    """New view for startups to share ideas generally (without a specific company)"""
    if request.method == 'POST':
        form = StartupRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            registration = form.save(commit=False)
            registration.user = request.user
            registration.company_name = "" # General share
            
            # Generate a unique 5-digit registration number
            reg_num = None
            while reg_num is None:
                candidate = f"{random.randint(10000, 99999):05d}"
                if not Registration.objects.filter(registration_number=candidate).exists():
                    reg_num = candidate
            registration.registration_number = reg_num

            # Generate a 5-character alphanumeric portal password
            alphabet = string.ascii_uppercase + string.digits
            portal_password = ''.join(random.choice(alphabet) for _ in range(5))
            registration.portal_password = portal_password

            registration.save()
            
            # Save team members
            team_names = request.POST.get('team_names', '')
            team_emails = request.POST.get('team_emails', '')
            names_list = [n.strip() for n in team_names.split(',') if n.strip()]
            emails_list = [e.strip() for e in team_emails.split(',') if e.strip()]
            from .models import TeamMember
            for name, email in zip(names_list, emails_list):
                TeamMember.objects.create(registration=registration, name=name, email=email)

            actual_count = len(names_list) + 1
            if actual_count > 1:
                registration.team_size = actual_count
            registration.save()
            
            # Trigger Background Verification for Startup Registration (General) synchronously
            from .tasks import run_startup_verification
            run_startup_verification(registration.id)
            
            request.session['registration_number'] = reg_num

            messages.success(request, "Your idea has been shared with all investors!")
            return redirect(f"{reverse('project_review:registration_success')}?type=general")
    else:
        form = StartupRegistrationForm()
        # Pre-fill fields from user/profile where available
        form.initial['email'] = request.user.email
        if request.user.first_name:
            form.initial['first_name'] = request.user.first_name
        if request.user.last_name:
            form.initial['last_name'] = request.user.last_name

    return render(request, 'project_review/share_ideas.html', {'form': form})


def registration_success_view(request):
    # Company is required to scope the success page
    company_name = request.GET.get('company')
    back_url = reverse('project_review:home')

    registration = None
    registration_number = None
    if company_name:
        registration_number = request.session.get(f'registration_number_{company_name}')
        # If not in session, try to fetch for authenticated user
        if not registration_number and request.user.is_authenticated:
            registration = Registration.objects.filter(user=request.user, company_name=company_name).order_by('-id').first()
            if registration:
                registration_number = registration.registration_number
                request.session[f'registration_number_{company_name}'] = registration_number
        elif registration_number:
            registration = Registration.objects.filter(registration_number=registration_number).first()
    else:
        # General share (no specific company)
        registration_number = request.session.get('registration_number')
        if registration_number:
            registration = Registration.objects.filter(registration_number=registration_number).first()
        elif request.user.is_authenticated:
            registration = Registration.objects.filter(user=request.user, company_name="").order_by('-id').first()
            if registration:
                registration_number = registration.registration_number

    # derive back_url based on company_name with robust fallback
    from .models import Company
    db_company = Company.objects.filter(name=company_name).first()
    if db_company:
        back_url = reverse('project_review:company_detail_dynamic', args=[db_company.pk])
    else:
        company_back_map = {
            'TCS': 'project_review:company',
            'IBM': 'project_review:company2',
            'Zoho': 'project_review:company3',
            'Cognizant': 'project_review:company_cognizant',
            'Amazon': 'project_review:company_amazon',
            'HCLTech': 'project_review:company_hcltech',
            'Infosys': 'project_review:company_infosys',
            'Wipro': 'project_review:company_wipro',
        }
        if company_name in company_back_map:
            back_url = reverse(company_back_map[company_name])
        else:
            back_url = reverse('project_review:home')

    context = {
        'registration_number': registration_number,
        'registration': registration,
        'company_name': company_name,
        'back_url': back_url,
    }
    return render(request, 'project_review/message.html', context)


@login_required
def startup_invoice_view(request):
    # Try to find a registration for the current user
    # If a registration_id is not provided, find the most recent one
    registration_id = request.GET.get('id')
    if registration_id:
        registration = get_object_or_404(Registration, id=registration_id)
        # Security: Only owner or admin can see it
        profile = getattr(request.user, 'profile', None)
        is_admin = profile and profile.role == UserProfile.ROLE_ADMIN
    # Pre-calculate values for the invoice to prevent template tag line-breaks
    founder_full_name = f"{registration.first_name} {registration.last_name}"
    similarity_score = f"{registration.idea_similarity_score:.1f}"
    authenticity_score = str(registration.idea_authenticity_score)
    patent_num = registration.patent_number.upper() if registration.patent_number else ""
    patent_registry = registration.patent_registry if registration.patent_registry else "Global Database"
    patent_owner = registration.patent_owner if registration.patent_owner else "Founders"
    patent_detailed_status = registration.patent_detailed_status if registration.patent_detailed_status else "Authenticated"
    recommended_action = registration.recommended_action if registration.recommended_action else "Strategic analysis is being finalized by the neural verification engine."
    
    # Calculate status color
    status_color = "#ef4444" 
    if registration.idea_status == 'Unique':
        status_color = "#10b981" 
    elif 'Partial' in str(registration.idea_status):
        status_color = "#f59e0b"

    context = {
        'registration': registration,
        'status_color': status_color,
        'founder_full_name': founder_full_name,
        'similarity_score': similarity_score,
        'authenticity_score': authenticity_score,
        'patent_num': patent_num,
        'patent_registry': patent_registry,
        'patent_owner': patent_owner,
        'patent_detailed_status': patent_detailed_status,
        'recommended_action': recommended_action,
    }

    return render(request, 'project_review/startup_invoice.html', context)


@login_required
@never_cache
def startup_idea_detail_view(request, pk):
    startup = get_object_or_404(Registration, pk=pk)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    # Permission logic
    is_owner = startup.user == request.user
    is_admin = profile.role == UserProfile.ROLE_ADMIN
    
    # Check if this user was targeted by a notification for this startup
    is_targeted_investor = PortalMessage.objects.filter(
        recipient=request.user, 
        registration=startup
    ).exists()

    # Check for general ideas eligibility
    is_eligible_investor = False
    if profile.role == UserProfile.ROLE_INVESTOR:
        # UPDATED: Allow all investors to view if it's a general idea (regardless of strength as requested)
        is_general_idea = not startup.company_name or startup.company_name.strip() == ""
        if is_general_idea:
            is_eligible_investor = True
            
    # Also check if the registration was specifically targeted to this user's company (by name)
    is_targeted_company = False
    company = request.user.companies.first()
    if company and startup.company_name == company.name:
        is_targeted_company = True
    
    if not (is_owner or is_admin or is_targeted_investor or is_eligible_investor or is_targeted_company):
        logger.warning("Permission denied for user %s on startup %s", request.user.username, pk)
        messages.error(request, "You do not have permission to view these details.")
        return redirect('project_review:home')
    
    # Mark relevant notifications as read
    PortalMessage.objects.filter(recipient=request.user, registration=startup, is_read=False).update(is_read=True)
    
    # Dynamic back URL based on where the user came from
    return_target = request.GET.get('return')
    if return_target == 'notifications':
        back_url = reverse('project_review:notifications')
    else:
        back_url = reverse('project_review:home')

    # NEW: Check if current investor has already accepted this startup
    is_accepted = PortalMessage.objects.filter(
        recipient=request.user,
        registration=startup,
        text__icontains="Strategic Partnership Confirmed"
    ).exists()

    return render(request, 'project_review/startup_idea_detail.html', {
        'startup': startup,
        'is_investor_view': profile.role == UserProfile.ROLE_INVESTOR,
        'is_accepted': is_accepted,
        'back_url': back_url
    })

@login_required
@require_POST
def startup_accept_view(request, pk):
    """View for an investor to accept a startup idea."""
    startup = get_object_or_404(Registration, pk=pk)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    if profile.role != UserProfile.ROLE_INVESTOR:
        messages.error(request, "Only investors can accept project ideas.")
        return redirect('project_review:home')

    # Check if already accepted
    if PortalMessage.objects.filter(recipient=request.user, registration=startup, text__icontains="Strategic Partnership Confirmed").exists():
        messages.info(request, "You have already accepted this project.")
        return redirect(reverse('project_review:startup_idea_detail', args=[pk]))

    # 1. Notify the Startup
    investor_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
    investor_company = request.user.companies.first()
    company_name = investor_company.name if investor_company else "an investor"
    
    if startup.user:
        PortalMessage.objects.create(
            recipient=startup.user,
            sender_name=investor_name,
            registration=startup,
            text=f"this company accepted your project idea: {company_name}"
        )

    # 2. Notify the Investor with Credentials
    reg_num = startup.registration_number
    pin = startup.portal_password
    PortalMessage.objects.create(
        recipient=request.user,
        sender_name='Gateway',
        registration=startup,
        text=f"Strategic Partnership Confirmed for '{startup.startup_name or startup.company_name}'. Access the secure portal using ID: {reg_num} and PIN: {pin}."
    )

    messages.success(request, f"You have accepted the project '{startup.startup_name or startup.company_name}'. credentials shared in your notifications.")
    return redirect(reverse('project_review:startup_idea_detail', args=[pk]))




def portal_validation_success_view(request):
    # Show a confirmation after successful portal validation
    reg_num = request.GET.get('reg')
    reg_obj = Registration.objects.filter(registration_number=reg_num).first()
    
    # Pre-calculate values to avoid complex template tags that might split across lines
    patent_registry = "Google Patents / WIPO"
    patent_owner = "Founders"
    patent_detailed_status = "Pending"
    
    show_certificate = False
    if reg_obj:
        print(f"DEBUG: View for {reg_num} -> status={reg_obj.idea_status}, score={reg_obj.idea_authenticity_score}, verify_status={reg_obj.project_verification_status}")
        if reg_obj.patent_registry: patent_registry = reg_obj.patent_registry
        if reg_obj.patent_owner: patent_owner = reg_obj.patent_owner
        if reg_obj.patent_detailed_status: patent_detailed_status = reg_obj.patent_detailed_status
        
        # Show certificate ONLY if score is 100
        if reg_obj.idea_authenticity_score == 100:
            show_certificate = True

    context = {
        'reg_obj': reg_obj,
        'registration_number': reg_num,
        'company_name': reg_obj.company_name if reg_obj else '',
        'user_name': (reg_obj.first_name or reg_obj.startup_name) if reg_obj else '',
        'patent_registry': patent_registry,
        'patent_owner': patent_owner,
        'patent_detailed_status': patent_detailed_status,
        'show_certificate': show_certificate,
    }
    return render(request, 'project_review/portal_validation_success.html', context)

@login_required
def view_certificate(request, pk):
    """View to display the earned integrity certificate."""
    reg_obj = get_object_or_404(Registration, pk=pk)
    
    # Security check
    profile = getattr(request.user, 'profile', None)
    if not (reg_obj.user == request.user or (profile and profile.role == UserProfile.ROLE_ADMIN)):
        messages.error(request, "Access denied.")
        return redirect('project_review:home')
        
    if reg_obj.idea_authenticity_score < 100:
        messages.warning(request, "This certificate is not yet available. Reach 100% Integrity Score to unlock.")
        return redirect(reverse('project_review:portal_validation_success') + f'?reg={reg_obj.registration_number}')
        
    context = {
        'reg_obj': reg_obj,
        'cert_date': timezone.now()
    }
    return render(request, 'project_review/certificate.html', context)


@require_POST
def emailjs_send_view(request):
    name = (request.POST.get('name') or '').strip()
    email = (request.POST.get('email') or '').strip()
    message = (request.POST.get('message') or '').strip()
    if not name or not email or not message:
        return JsonResponse({"success": False, "error": "name, email, and message are required"}, status=400)
    tpl = getattr(settings, 'EMAILJS_TEMPLATE_ID_CONTACT', '') or getattr(settings, 'EMAILJS_TEMPLATE_ID_REG', '')
    params = {
        "from_name": name,
        "reply_to": email,
        "message": message,
        "to_email": email,
    }
    ok = send_emailjs_email(params, getattr(settings, 'EMAILJS_SERVICE_ID', ''), tpl, getattr(settings, 'EMAILJS_PUBLIC_KEY', ''))
    if ok:
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Failed to send email"}, status=502)


@require_POST
def emailjs_registration_view(request):
    email = (request.POST.get('email') or '').strip()
    registration_number = (request.POST.get('registration_number') or '').strip()
    company_name = (request.POST.get('company_name') or '').strip()
    password = (request.POST.get('password') or '').strip()
    if not email or not registration_number or not company_name or not password:
        return JsonResponse({"success": False, "error": "email, registration_number, company_name, password are required"}, status=400)
    origin = f"{request.scheme}://{request.get_host()}"
    ok = send_registration_email(email, registration_number, company_name, password, getattr(settings, 'EMAILJS_SERVICE_ID_REG', ''), getattr(settings, 'EMAILJS_TEMPLATE_ID_REG', ''), getattr(settings, 'EMAILJS_PUBLIC_KEY', ''), origin=origin)
    if ok:
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Failed to send registration email"}, status=502)

# Admin Views
def admin_required(view_func):
    """Decorator for views that checks that the user is logged in and is an admin."""
    @login_required
    @never_cache
    def _wrapped_view(request, *args, **kwargs):
        if hasattr(request.user, 'profile') and request.user.profile.role == UserProfile.ROLE_ADMIN:
            return view_func(request, *args, **kwargs)
        messages.error(request, "You are not authorized to view the admin dashboard.")
        return redirect('project_review:home')
    return _wrapped_view

@admin_required
def admin_dashboard_view(request):
    # Only fast count queries for the initial page load
    total_startups = Registration.objects.count()
    total_investors = Company.objects.count()
    total_users = User.objects.count()

    context = {
        'total_startups': total_startups,
        'total_investors': total_investors,
        'total_users': total_users,
        'title': 'Admin Dashboard Overview'
    }
    return render(request, 'project_review/admin_dashboard.html', context)

@admin_required
def api_admin_dashboard_stats(request):
    """API endpoint to fetch chart data asynchronously for better performance."""
    # 1. Startup Categories (Pie Chart)
    category_data = Registration.objects.values('category').annotate(count=Count('id')).order_by('-count')
    category_labels = [item['category'] or 'Other' for item in category_data]
    category_counts = [item['count'] for item in category_data]

    # 2. Startup Registrations (Monthly)
    startup_monthly = Registration.objects.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month')
    # Limit to last 12 months for performance
    startup_monthly = list(startup_monthly)[-12:]
    s_monthly_labels = [item['month'].strftime('%b %Y') for item in startup_monthly]
    s_monthly_counts = [item['count'] for item in startup_monthly]

    # 3. Investor Registrations (Monthly)
    investor_monthly = Company.objects.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month')
    investor_monthly = list(investor_monthly)[-12:]
    i_monthly_labels = [item['month'].strftime('%b %Y') for item in investor_monthly]
    i_monthly_counts = [item['count'] for item in investor_monthly]

    return JsonResponse({
        'categories': {'labels': category_labels, 'counts': category_counts},
        'startups': {'labels': s_monthly_labels, 'counts': s_monthly_counts},
        'investors': {'labels': i_monthly_labels, 'counts': i_monthly_counts}
    })

@admin_required
def admin_startup_list_view(request):
    from django.core.paginator import Paginator
    query = request.GET.get('q', '')
    startups = Registration.objects.all().order_by('-created_at')
    if query:
        startups = startups.filter(
            Q(startup_name__icontains=query) |
            Q(registration_number__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )
    
    paginator = Paginator(startups, 10) # 10 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'project_review/admin_startup_list.html', {
        'startups': page_obj, 
        'query': query,
        'total_count': startups.count()
    })

@admin_required
def admin_investor_list_view(request):
    from django.core.paginator import Paginator
    query = request.GET.get('q', '').strip()
    
    # NEW: Fetch ALL Users with the 'investor' role, ensuring even those without Company records are seen
    investor_users = User.objects.filter(profile__role=UserProfile.ROLE_INVESTOR).select_related('profile').prefetch_related('companies').order_by('-date_joined')
    
    if query:
        investor_users = investor_users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(companies__name__icontains=query)
        ).distinct()
    
    paginator = Paginator(investor_users, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'project_review/admin_investor_list.html', {
        'investor_users': page_obj, 
        'query': query,
        'total_count': investor_users.count()
    })

@admin_required
def admin_user_list_view(request):
    from django.core.paginator import Paginator
    query = request.GET.get('q', '')
    # Fetch all users with their roles from profiles
    users = User.objects.all().select_related('profile').order_by('-date_joined')
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )
    
    paginator = Paginator(users, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'project_review/admin_user_list.html', {
        'users': page_obj, 
        'query': query,
        'total_count': users.count()
    })

@admin_required
def admin_startup_detail_view(request, pk):
    startup = get_object_or_404(Registration, pk=pk)
    return render(request, 'project_review/admin_startup_detail.html', {'startup': startup})

@admin_required
def admin_investor_detail_view(request, pk):
    company = get_object_or_404(Company, pk=pk)
    user = company.user
    profile = getattr(user, 'profile', None)
    
    return render(request, 'project_review/admin_investor_detail.html', {
        'company': company,
        'user': user,
        'profile': profile
    })

@admin_required
def admin_user_detail_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    login_history = LoginHistory.objects.filter(user=user).order_by('-login_time')
    return render(request, 'project_review/admin_user_detail.html', {
        'target_user': user,
        'login_history': login_history
    })

@admin_required
@require_POST
def admin_delete_user_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    
    # Don't allow deleting yourself
    if user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect('project_review:admin_user_list')

    # Backup data to DeletedUserRecord
    profile = getattr(user, 'profile', None)
    role = profile.role if profile else 'unknown'
    phone = profile.phone_number if profile else ''
    loc = profile.location if profile else ''
    
    # Try to find a portal password from Registration
    reg = Registration.objects.filter(user=user).first()
    portal_password = reg.portal_password if reg else None
    
    DeletedUserRecord.objects.create(
        username=user.username,
        email=user.email,
        role=role,
        phone_number=phone,
        location=loc,
        date_joined=user.date_joined,
        last_login=user.last_login,
        password_hash=user.password,
        portal_password=portal_password,
        plain_text_password=profile.plain_text_password if profile else None,
        reason=request.POST.get('reason', 'Administrative deletion')
    )
    
    # Now delete the user
    username = user.username
    user.delete()
    
    messages.success(request, f"User {username} has been deleted and archived.")
    return redirect('project_review:admin_user_list')

@admin_required
def admin_deleted_records_view(request):
    records = DeletedUserRecord.objects.all().order_by('-deleted_at')
    return render(request, 'project_review/admin_deleted_records.html', {
        'records': records,
        'title': 'Deleted User Records Archive'
    })

@admin_required
@require_POST
def admin_restore_user_view(request, pk):
    record = get_object_or_404(DeletedUserRecord, pk=pk)
    
    # Check if username or email already exists
    if User.objects.filter(username=record.username).exists():
        messages.error(request, f"Cannot restore: Username '{record.username}' is already in use by another account.")
        return redirect('project_review:admin_deleted_records')
        
    if User.objects.filter(email=record.email).exists():
        messages.error(request, f"Cannot restore: Email '{record.email}' is already in use by another account.")
        return redirect('project_review:admin_deleted_records')

    # Create the user
    user = User.objects.create(
        username=record.username,
        email=record.email,
        date_joined=record.date_joined,
        last_login=record.last_login
    )
    
    # Set the archived password hash directly
    if record.password_hash:
        user.password = record.password_hash
        user.save()
    else:
        # If no hash saved (from previous version), set a default
        user.set_password('Gateway@123')
        user.save()

    # Create Profile
    UserProfile.objects.get_or_create(
        user=user,
        role=record.role,
        phone_number=record.phone_number,
        location=record.location,
        plain_text_password=record.plain_text_password
    )
    
    # If they had a portal password, restore a placeholder Registration
    if record.role == 'startup' and record.portal_password:
        reg_num = get_random_string(5, allowed_chars='0123456789')
        Registration.objects.create(
            user=user,
            email=record.email,
            portal_password=record.portal_password,
            registration_number=reg_num,
            startup_name=record.username,
            company_name=record.username
        )

    # Delete the archive record
    record.delete()
    
    messages.success(request, f"User {user.username} has been restored successfully.")
    return redirect('project_review:admin_user_list')


@login_required
def registration_portal_view(request):
    # Only for startups
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role != UserProfile.ROLE_STARTUP:
        messages.error(request, "This page is only accessible to startup users.")
        return redirect('project_review:home')
    
    # Get all registrations for this user
    registrations = Registration.objects.filter(user=request.user).order_by('-created_at')
    
    # For each registration, find related approval messages (notifications)
    reg_data = []
    for reg in registrations:
        # Related notifications about this registration
        notifs = PortalMessage.objects.filter(registration=reg).order_by('-timestamp')
        
        # Determine current status based on messages
        # If there's a message saying 'approved', it's approved
        is_approved = notifs.filter(text__icontains='approved').exists()
        
        reg_data.append({
            'registration': reg,
            'notifications': notifs,
            'is_approved': is_approved,
            'approval_count': notifs.filter(text__icontains='approved').count()
        })
    
    return render(request, 'project_review/registration_portal.html', {
        'reg_data': reg_data
    })


# ── Verification & Trust Scoring API ──────────────────────────────────────────

from .tasks import run_investor_verification, run_startup_verification, run_startup_profile_verification

@login_required
def trigger_verification_view(request, role, pk):
    """
    Manual trigger for verification tasks via API.
    """
    from .models import Company, Registration, UserProfile
    
    if role == 'investor':
        try:
            company = Company.objects.get(pk=pk)
            run_investor_verification(company.id)
            return JsonResponse({'status': 'Verification triggered for investor.'})
        except Company.DoesNotExist:
            return JsonResponse({'error': 'Investor not found.'}, status=404)
    elif role == 'startup_reg':
        try:
            reg = Registration.objects.get(pk=pk)
            run_startup_verification(reg.id)
            return JsonResponse({'status': 'Verification triggered for registration.'})
        except Registration.DoesNotExist:
            return JsonResponse({'error': 'Registration not found.'}, status=404)
    elif role == 'startup_profile':
        try:
            profile = UserProfile.objects.get(pk=pk)
            run_startup_profile_verification(profile.id)
            return JsonResponse({'status': 'Verification triggered for startup profile.'})
        except UserProfile.DoesNotExist:
            return JsonResponse({'error': 'Profile not found.'}, status=404)
            
    return JsonResponse({'error': 'Invalid role.'}, status=400)

@login_required
@require_POST
def admin_approve_investor(request, pk):
    """Admin manual approval for an investor profile."""
    # Ensure user is staff
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden.'}, status=403)
        
    from .models import Company
    from .services import verification as verify_service
    company = get_object_or_404(Company, pk=pk)
    company.admin_approved = True
    company.admin_note = request.POST.get('note', '')
    
    # Recalculate score with bonus
    company.trust_score = verify_service.calculate_investor_trust_score(company)
    company.verification_status = verify_service.get_verification_status_label(company.trust_score)
    company.save()
    
    messages.success(request, f"Investor '{company.name}' has been manually approved.")
    return redirect('project_review:admin_investor_detail', pk=pk)

@login_required
@require_POST
def admin_reject_investor(request, pk):
    """Admin manual rejection for an investor profile."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden.'}, status=403)

    from .models import Company
    from .services import verification as verify_service
    company = get_object_or_404(Company, pk=pk)
    company.admin_approved = False
    company.admin_note = request.POST.get('note', '')
    
    # Recalculate score
    company.trust_score = verify_service.calculate_investor_trust_score(company)
    company.verification_status = verify_service.get_verification_status_label(company.trust_score)
    company.save()
    
    messages.warning(request, f"Investor '{company.name}' has been marked as rejected.")
    return redirect('project_review:admin_investor_detail', pk=pk)

@login_required
def patent_services_view(request, pk):
    """
    Handles request for patent services and document upload for 50% startups.
    """
    from .models import Registration
    from .tasks import run_background_verification
    reg = get_object_or_404(Registration, pk=pk)
    
    if request.method == 'POST':
        patent_file = request.FILES.get('patent_file')
        if patent_file:
            reg.patent_file = patent_file
            # Reset verification status to re-trigger analysis
            reg.verification_completed = False
            reg.patent_status = 'Pending'
            reg.save()
            
            # Re-trigger background task to scan NEW document
            run_background_verification(reg.id)
            
            messages.success(request, "Patent document uploaded successfully. Our AI is re-analyzing your IP.")
            return redirect('project_review:portal_validation_success')
            
        messages.error(request, "Please select a valid document to upload.")

    return render(request, 'project_review/portal_validation_success.html', {
        'reg_obj': reg,
        'patent_service_active': True
    })

@login_required
def unread_counts_api(request):
    """API endpoint to get live unread counts for notifications and messages."""
    from .models import PortalMessage, DirectMessage
    from django.db.models import Q
    
    # Notifications (System + Registration targeted)
    unread_notifications = PortalMessage.objects.filter(
        recipient=request.user, 
        is_read=False
    ).filter(Q(sender_name='System') | Q(registration__isnull=False)).count()
    
    # User messages (PortalMessages exclude System/Reg + DirectMessages)
    portal_msg_count = PortalMessage.objects.filter(
        recipient=request.user, 
        is_read=False
    ).exclude(Q(sender_name='System') | Q(registration__isnull=False)).count()
    
    direct_msg_count = DirectMessage.objects.filter(
        recipient=request.user, 
        is_read=False
    ).count()
    
    return JsonResponse({
        'unread_notifications_count': unread_notifications,
        'unread_messages_count': portal_msg_count + direct_msg_count,
    })

