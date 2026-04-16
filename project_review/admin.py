from django.contrib import admin
from .models import UserProfile, Company, Registration, LoginHistory, PortalMessage, TeamMember

@admin.register(PortalMessage)
class PortalMessageAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'sender_name', 'timestamp', 'is_read')
    list_filter = ('timestamp', 'is_read')
    search_fields = ('recipient__username', 'text')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username',)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'role_in_company', 'created_at', 'promoted')
    list_filter = ('promoted', 'created_at')
    search_fields = ('name', 'user__username', 'role_in_company')

class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 1



@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('registration_number', 'startup_name', 'company_name', 'email', 'created_at', 'team_size')
    search_fields = ('registration_number', 'company_name', 'email', 'startup_name')
    list_filter = ('created_at', 'category')
    inlines = [TeamMemberInline]

@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'login_time')
    search_fields = ('username', 'email')


