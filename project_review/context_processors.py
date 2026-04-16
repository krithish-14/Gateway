from .models import PortalMessage

def notification_counts(request):
    if request.user.is_authenticated:
        from django.db.models import Q
        # BROADENED: Notifications are either from 'System' OR regarding a specific Registration
        unread_notifications = PortalMessage.objects.filter(
            recipient=request.user, 
            is_read=False
        ).filter(Q(sender_name='System') | Q(registration__isnull=False)).count()
        
        # User messages (PortalMessages exclude System/Reg + DirectMessages)
        portal_msg_count = PortalMessage.objects.filter(
            recipient=request.user, 
            is_read=False
        ).exclude(Q(sender_name='System') | Q(registration__isnull=False)).count()
        
        from .models import DirectMessage
        direct_msg_count = DirectMessage.objects.filter(
            recipient=request.user, 
            is_read=False
        ).count()
        
        return {
            'unread_notifications_count': unread_notifications,
            'unread_messages_count': portal_msg_count + direct_msg_count,
        }
    return {
        'unread_notifications_count': 0,
        'unread_messages_count': 0,
    }
