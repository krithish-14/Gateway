from django.urls import path
from . import views

app_name = 'project_review'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/<str:token>/', views.reset_password_view, name='reset_password'),
    path('home/', views.home_view, name='home'),
    # New sections
    path('profile/', views.profile_view, name='profile'),
    path('startup-idea-detail/<int:pk>/', views.startup_idea_detail_view, name='startup_idea_detail'),
    path('startup-idea-detail/<int:pk>/accept/', views.startup_accept_view, name='startup_accept'),
    path('search-domain/', views.domain_search_view, name='search_domain'),
    # Alias to support underscore path in case users navigate to /search_domain/
    path('search_domain/', views.domain_search_view, name='search_domain_alias'),
    path('portal/', views.portal_view, name='portal'),
    # Alias to support /project_review/portal/ when app is included at root
    path('project_review/portal/', views.portal_view, name='portal_alias'),
    path('portal/validated/', views.portal_validation_success_view, name='portal_validation_success'),
    path('about/', views.about_view, name='about'),
    # Notifications and Messages pages
    path('notifications/', views.notifications_view, name='notifications'),
    path('messages/', views.messages_view, name='messages'),
    # Existing pages (legacy/demo)
    path('company/', views.company_view, name='company'),
    path('company2/', views.company2_view, name='company2'),
    path('company3/', views.company3_view, name='company3'),
    # New company detail pages
    path('company/cognizant/', views.company_cognizant_view, name='company_cognizant'),
    path('company/amazon/', views.company_amazon_view, name='company_amazon'),
    path('company/hcltech/', views.company_hcltech_view, name='company_hcltech'),
    path('company/infosys/', views.company_infosys_view, name='company_infosys'),
    path('company/wipro/', views.company_wipro_view, name='company_wipro'),
    # Startup Registration page (new)
    path('startup-registration/', views.startup_registration_view, name='startup_registration'),
    path('share-ideas/', views.share_ideas_view, name='share_ideas'),
    # Success message page after registration (missing route added)
    path('registration-success/', views.registration_success_view, name='registration_success'),
    path('startup-invoice/', views.startup_invoice_view, name='startup_invoice'),
    path('company/<int:pk>/', views.company_detail_view, name='company_detail_dynamic'),

    path('api/email/send/', views.emailjs_send_view, name='emailjs_send'),
    path('api/email/registration/', views.emailjs_registration_view, name='emailjs_registration'),
    path('api/messages/chat/<int:user_id>/', views.api_get_chat, name='api_get_chat'),
    path('api/messages/send/', views.api_send_message, name='api_send_message'),
    
    # Admin routes
    path('api/admin/dashboard-stats/', views.api_admin_dashboard_stats, name='api_admin_dashboard_stats'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-dashboard/startups/', views.admin_startup_list_view, name='admin_startup_list'),
    path('admin-dashboard/investors/', views.admin_investor_list_view, name='admin_investor_list'),
    path('admin-dashboard/users/', views.admin_user_list_view, name='admin_user_list'),
    path('admin-dashboard/startup/<int:pk>/', views.admin_startup_detail_view, name='admin_startup_detail'),
    path('admin-dashboard/investor/<int:pk>/', views.admin_investor_detail_view, name='admin_investor_detail'),
    path('admin-dashboard/user/<int:pk>/', views.admin_user_detail_view, name='admin_user_detail'),
    path('admin-dashboard/user/<int:pk>/delete/', views.admin_delete_user_view, name='admin_delete_user'),
    path('admin-dashboard/deleted-records/', views.admin_deleted_records_view, name='admin_deleted_records'),
    path('notification/<int:msg_id>/confirm/', views.notification_confirm_view, name='notification_confirm'),
    path('notification/<int:msg_id>/decline/', views.notification_decline_view, name='notification_decline'),
    path('notification/<int:msg_id>/read/', views.mark_as_read_view, name='mark_as_read'),
    path('registration-portal/', views.registration_portal_view, name='registration_portal'),
    path('admin-dashboard/deleted-records/<int:pk>/restore/', views.admin_restore_user_view, name='admin_restore_user'),

    # Verification & Trust Scoring
    path('api/verify/<str:role>/<int:pk>/trigger/', views.trigger_verification_view, name='trigger_verification'),
    path('admin-dashboard/investor/<int:pk>/approve/', views.admin_approve_investor, name='admin_approve_investor'),
    path('admin-dashboard/investor/<int:pk>/reject/', views.admin_reject_investor, name='admin_reject_investor'),
    path('portal/patent-services/<int:pk>/', views.patent_services_view, name='patent_services'),
    path('portal/certificate/<int:pk>/', views.view_certificate, name='view_certificate'),
    path('api/unread-counts/', views.unread_counts_api, name='api_unread_counts'),
    path('chatbot/', views.chatbot_view, name='chatbot'),
    path('api/chatbot/ask/', views.api_chatbot_ask, name='api_chatbot_ask'),
    path('api/chatbot/history/', views.api_chatbot_history, name='api_chatbot_history'),
]

