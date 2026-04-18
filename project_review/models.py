from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    ROLE_STARTUP = 'startup'
    ROLE_INVESTOR = 'investor'
    ROLE_ADMIN = 'admin'
    ROLE_CHOICES = [
        (ROLE_STARTUP, 'Startup'),
        (ROLE_INVESTOR, 'Investor'),
        (ROLE_ADMIN, 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_STARTUP, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    profile_image = models.ImageField(upload_to='project_review/profile_photos/', blank=True, null=True)
    plain_text_password = models.CharField(max_length=128, blank=True, null=True, help_text="Stored for admin visibility")
    
    # Startup specific fields
    current_address = models.TextField(blank=True, null=True)
    startup_website = models.URLField(blank=True, null=True)
    startup_linkedin = models.URLField(blank=True, null=True)
    github_profile = models.URLField(blank=True, null=True)
    startup_category = models.CharField(max_length=100, blank=True, null=True)

    # Startup Patent Verification
    patent_number = models.CharField(max_length=50, blank=True, null=True)
    patent_verified = models.BooleanField(default=False)
    patent_status = models.CharField(
        max_length=20, 
        choices=[('Verified', 'Verified'), ('Invalid', 'Invalid'), ('Pending', 'Pending'), ('Not Provided', 'Not Provided')],
        default='Not Provided'
    )
    trust_score = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.user.username} - {self.get_role_display()}'

    @property
    def investor_completion_breakdown(self):
        if self.role != self.ROLE_INVESTOR:
            return None
            
        company = self.user.companies.first()
        
        # 1. Personal Information (20%) - Includes User info + Company Identity
        # Fields: First Name, Last Name, Email, Phone, Location, Company Name, Role in Company
        personal_fields = [
            self.user.first_name, self.user.last_name, self.user.email, 
            self.phone_number, self.location,
            (company.name if company else None),
            (company.role_in_company if company else None)
        ]
        filled_personal = sum(1 for f in personal_fields if f)
        personal_score = (filled_personal / 7) * 20
        
        # 2. Professional Links (40%) - Includes digital presence and verification
        # GST given highest weight (30%) compared to digital links (5% each)
        prof_score = 0
        if company:
            if company.website: prof_score += 5
            if company.linkedin_profile: prof_score += 5
            if company.gst_verified: prof_score += 30
        
        # 3. About & Experience (30%) - Narrative and focus
        # Fields: About (15%), Investment Focus (15%)
        about_score = 0
        if company:
            if company.about: about_score += 15
            if company.investment_focus: about_score += 15
            
        # 4. Photo Management (10%) - Visual identity
        # Fields: Profile Photo (5%), Company Logo (5%)
        photo_score = 0
        if self.profile_image: photo_score += 5
        if company and company.logo: photo_score += 5
        
        return {
            'personal': int(personal_score),
            'professional': int(prof_score),
            'about': int(about_score),
            'photo': int(photo_score),
            'total': int(personal_score + prof_score + about_score + photo_score)
        }

    @property
    def completion_percentage(self):
        if self.role == self.ROLE_INVESTOR:
            breakdown = self.investor_completion_breakdown
            return breakdown['total'] if breakdown else 0
        
        # For startups
        fields_to_check = [
            'phone_number', 'location', 'profile_image',
            'current_address', 'startup_website', 'startup_category'
        ]
        # Adding User fields to check as well
        filled_count = 0
        if self.user.first_name: filled_count += 1
        if self.user.last_name: filled_count += 1
        if self.user.email: filled_count += 1
        
        total_fields = len(fields_to_check) + 3 # +3 for first_name, last_name, email
        
        for field in fields_to_check:
            val = getattr(self, field, None)
            if val:
                filled_count += 1
                
        return int((filled_count / total_fields) * 100)

class Company(models.Model):
    # Base fields
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='project_review/company_logos/', blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    rating_count = models.IntegerField(default=0)
    price_range = models.CharField(max_length=10, blank=True, null=True)
    category = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    promoted = models.BooleanField(default=False, db_index=True)

    # Investor / Detailed Profile fields
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='companies')
    role_in_company = models.CharField(max_length=255, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    linkedin_profile = models.URLField(blank=True, null=True)
    about = models.TextField(blank=True, null=True)
    investment_focus = models.TextField(blank=True, null=True)
    gst_invoice = models.FileField(upload_to='project_review/investor_invoices/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Verification Fields ───────────────────────────────────────────────────
    # LinkedIn verification
    linkedin_verified = models.BooleanField(default=False)
    linkedin_last_checked = models.DateTimeField(null=True, blank=True)

    # Website verification
    WEBSITE_STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Unreachable', 'Unreachable'),
        ('Suspicious', 'Suspicious'),
        ('Unknown', 'Unknown'),
    ]
    website_verified = models.BooleanField(default=False)
    website_status = models.CharField(max_length=20, choices=WEBSITE_STATUS_CHOICES, default='Unknown')

    # GST Invoice verification
    GST_VERIFICATION_CHOICES = [
        ('Verified', 'Verified'),
        ('Invalid', 'Invalid'),
        ('Pending', 'Pending'),
        ('Not Uploaded', 'Not Uploaded'),
    ]
    gstin_number = models.CharField(max_length=20, blank=True)
    gst_verified = models.BooleanField(default=False)
    gst_extracted_from_invoice = models.BooleanField(default=False)
    gst_verification_status = models.CharField(
        max_length=20, choices=GST_VERIFICATION_CHOICES, default='Not Uploaded'
    )
    # Extra GST metadata from API
    gst_legal_name = models.CharField(max_length=255, blank=True)
    gst_registration_date = models.CharField(max_length=50, blank=True)
    gst_center_state = models.CharField(max_length=100, blank=True)
    gst_taxpayer_type = models.CharField(max_length=50, blank=True)

    # Trust Score & Overall Status
    VERIFICATION_STATUS_CHOICES = [
        ('Verified Profile', 'Verified Profile'),
        ('Needs Review', 'Needs Review'),
        ('Suspicious', 'Suspicious'),
        ('Unverified', 'Unverified'),
    ]
    trust_score = models.IntegerField(default=0)
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='Unverified'
    )

    # Admin manual approval
    admin_approved = models.BooleanField(null=True, blank=True)  # None=pending, True=ok, False=rejected
    admin_note = models.TextField(blank=True)
    # ─────────────────────────────────────────────────────────────────────────

    def __str__(self):
        return self.name

    @property
    def completion_percentage(self):
        fields_to_check = [
            'name', 'logo', 'location', 'phone', 'category',
            'role_in_company', 'website', 'linkedin_profile',
            'about', 'investment_focus'
        ]
        filled_count = 0
        for field in fields_to_check:
            val = getattr(self, field)
            if val:
                filled_count += 1

        return (filled_count / len(fields_to_check)) * 100

    @property
    def is_eligible(self):
        """
        Criteria: GST invoice uploaded AND investor's Profile Strength >= 80%.
        Uses UserProfile.completion_percentage (the same score shown on the
        profile page) so the threshold is consistent with what the investor sees.
        Falls back to Company.completion_percentage if no linked UserProfile exists.
        """
        has_gst = bool(self.gst_invoice)
        if not has_gst:
            return False

        # Use the UserProfile's completion_percentage (Profile Strength) if available
        if self.user:
            try:
                profile_strength = self.user.profile.completion_percentage
                return profile_strength >= 80
            except Exception:
                pass

        # Fallback: use the Company-level completion percentage
        return self.completion_percentage >= 80

class Registration(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    registration_number = models.CharField(max_length=5, unique=True, db_index=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)
    team_size = models.IntegerField(default=1)
    profile_text = models.TextField(blank=True, help_text="Startup Description", db_index=False)
    startup_name = models.CharField(max_length=255, blank=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    portal_password = models.CharField(max_length=5, blank=True)
    startup_idea_report = models.FileField(upload_to='project_review/startup_reports/', blank=True, null=True)
    file_type = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    # ── Startup Verification & Analysis Fields ────────────────────────────────
    PATENT_STATUS_CHOICES = [
        ('Verified', 'Verified'),
        ('Invalid', 'Invalid'),
        ('Pending', 'Pending'),
        ('Not Submitted', 'Not Submitted'),
        ('Not Provided', 'Not Provided'),
    ]
    IDEA_STATUS_CHOICES = [
        ('Unique', 'Unique Idea'),
        ('Similar', 'Similar Idea Exists'),
        ('Duplicate', 'Duplicate Idea'),
        ('Pending', 'Pending Analysis'),
    ]
    VERIFICATION_STATUS_CHOICES = [
        ('Verified', 'Verified Project'),
        ('Patent Recommended', 'Patent Recommended'),
        ('Similar Found', 'Similar Ideas Found'),
        ('Rejected', 'Rejected'),
        ('Patent Failed', 'Patent Verification Failed'),
        ('Pending', 'In Progress'),
    ]

    patent_number = models.CharField(max_length=50, blank=True)
    patent_file = models.FileField(upload_to='project_review/patent_docs/', blank=True, null=True)
    patent_verified = models.BooleanField(default=False)
    patent_status = models.CharField(
        max_length=20, choices=PATENT_STATUS_CHOICES, default='Not Provided'
    )
    
    idea_similarity_score = models.FloatField(default=0.0)
    idea_status = models.CharField(max_length=20, choices=IDEA_STATUS_CHOICES, default='Pending')
    idea_authenticity_score = models.IntegerField(default=0)
    
    project_verification_status = models.CharField(
        max_length=30, choices=VERIFICATION_STATUS_CHOICES, default='Pending'
    )
    recommended_action = models.TextField(blank=True)
    verification_completed = models.BooleanField(default=False)
    
    # Internal analysis data
    extracted_summary_text = models.TextField(blank=True)
    generated_keywords = models.TextField(blank=True, help_text="Comma-separated keywords")
    
    trust_score = models.IntegerField(default=0)
    
    # New patent metadata fields
    patent_owner = models.CharField(max_length=255, blank=True, default="Unknown")
    patent_detailed_status = models.CharField(max_length=100, blank=True, default="In Processing")
    patent_registry = models.CharField(max_length=100, blank=True, default="Unknown Registry")
    # ─────────────────────────────────────────────────────────────────────────

    def __str__(self):
        return f"{self.registration_number} - {self.startup_name or self.company_name}"


class TeamMember(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='team_members')
    name = models.CharField(max_length=255)
    email = models.EmailField()

    def __str__(self):
        return f"{self.name} ({self.registration.registration_number})"




class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"ResetToken({self.user.username})"


class GatewayLogin(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    role = models.CharField(max_length=20, blank=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gateway_login'

    def __str__(self):
        return self.username


class LoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    username = models.CharField(max_length=150)
    email = models.EmailField(max_length=255, blank=True, null=True)
    login_time = models.DateTimeField(default=timezone.now)
    is_registered = models.IntegerField(default=0)  # 0 for first login, 1 for subsequent

    def __str__(self):
        return f"{self.username} ({self.email}) - {self.login_time}"


class PortalMessage(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    sender_name = models.CharField(max_length=100, default='System')
    registration = models.ForeignKey(Registration, on_delete=models.SET_NULL, null=True, blank=True, related_name='portal_messages')
    text = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)


    def __str__(self):
        return f"To: {self.recipient.username} - {self.text[:20]}..."


class DeletedUserRecord(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField()
    role = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    date_joined = models.DateTimeField()
    last_login = models.DateTimeField(null=True, blank=True)
    password_hash = models.CharField(max_length=128, blank=True, null=True)
    deleted_at = models.DateTimeField(auto_now_add=True)
    # Storing portal password if it exists (from Registration model)
    portal_password = models.CharField(max_length=128, blank=True, null=True)
    plain_text_password = models.CharField(max_length=128, blank=True, null=True)
    reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.username} (Deleted on {self.deleted_at})"


class DirectMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_dms')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_dms')
    body = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"From {self.sender.username} to {self.recipient.username}: {self.body[:20]}"

class AIChatMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_chats', db_index=True)
    message = models.TextField()
    response = models.TextField()
    intent_tag = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['intent_tag']),
        ]

    def __str__(self):
        return f"AI Chat ({self.intent_tag}) with {self.user.username} at {self.timestamp}"
