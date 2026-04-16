from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Registration

class StartupRegistrationForm(forms.ModelForm):
    # Make email required at the form level (even if model allows blank)
    email = forms.EmailField(required=True)
    # Using CharField here so it can accept string options like "1-5 Members" from the template
    team_size = forms.CharField(required=False)

    class Meta:
        model = Registration
        fields = ['company_name', 'category', 'team_size', 'profile_text', 'startup_name', 'first_name', 'last_name', 'email', 'startup_idea_report', 'file_type', 'patent_number', 'patent_file']
        labels = {
            'profile_text': 'Startup Description',
        }

    def clean_team_size(self):
        data = self.cleaned_data.get('team_size', '1')
        if not data:
            return 1
        # Extract number from string like "1-5 Members"
        try:
            if '-' in data:
                return int(data.split('-')[0])
            return int(data.split()[0])
        except (ValueError, IndexError):
            return 1




class ProfileForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=20, required=False)
    location = forms.CharField(max_length=255, required=False)
    new_password = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))
    profile_image = forms.ImageField(required=False)
    
    # Investor fields
    company_name = forms.CharField(max_length=255, required=False)
    about_company = forms.CharField(widget=forms.Textarea, required=False)
    company_website = forms.URLField(required=False)
    linkedin_profile = forms.URLField(required=False)
    gst_invoice = forms.FileField(required=False)
    investment_focus = forms.CharField(widget=forms.Textarea, required=False)
    investor_role_in_company = forms.CharField(max_length=255, required=False)
    company_logo = forms.ImageField(required=False)
    
    # Startup fields
    current_address = forms.CharField(widget=forms.Textarea, required=False)
    startup_website = forms.URLField(required=False, label="Portfolio")
    github_profile = forms.URLField(required=False)
    
    # Shared or context-dependent fields
    company_category = forms.CharField(max_length=255, required=False)

    def initialize_from_user(self, user: User):
        profile = getattr(user, 'profile', None)
        # For investors, try to pull data from their associated Company record
        company = None
        if profile and profile.role == UserProfile.ROLE_INVESTOR:
            company = user.companies.first()

        self.initial.update({
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone_number': getattr(profile, 'phone_number', ''),
            'location': getattr(profile, 'location', ''),
            'company_name': getattr(company, 'name', '') if company else getattr(profile, 'company_name', ''),
            'about_company': getattr(company, 'about', '') if company else getattr(profile, 'about_company', ''),
            'company_website': getattr(company, 'website', '') if company else getattr(profile, 'company_website', ''),
            'linkedin_profile': getattr(company, 'linkedin_profile', '') if company else getattr(profile, 'linkedin_profile', ''),
            'investment_focus': getattr(company, 'investment_focus', '') if company else getattr(profile, 'investment_focus', ''),
            'investor_role_in_company': getattr(company, 'role_in_company', '') if company else getattr(profile, 'investor_role_in_company', ''),
            'current_address': getattr(profile, 'current_address', ''),
            'startup_website': getattr(profile, 'startup_website', ''),
            'startup_linkedin': getattr(profile, 'startup_linkedin', ''),
            'github_profile': getattr(profile, 'github_profile', ''),
            'linkedin_profile': getattr(company, 'linkedin_profile', '') if company else getattr(profile, 'startup_linkedin', ''),
            'company_category': getattr(company, 'category', '') if company else getattr(profile, 'startup_category', ''),
        })