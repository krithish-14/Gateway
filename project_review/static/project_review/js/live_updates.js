/**
 * Live Updates Script
 * Polls the unread counts API and updates UI badges in real-time.
 * Displays a toast notification when a new alert or message is received.
 */

let lastNotifCount = null;
let lastMsgCount = null;

function updateBadges() {
    fetch('/api/unread-counts/')
        .then(response => response.json())
        .then(data => {
            const currentNotifCount = data.unread_notifications_count;
            const currentMsgCount = data.unread_messages_count;

            // Initial load: just store the values
            if (lastNotifCount === null) {
                lastNotifCount = currentNotifCount;
                lastMsgCount = currentMsgCount;
                return;
            }

            // check for NEW notifications
            if (currentNotifCount > lastNotifCount) {
                showLiveToast('Gateway Notification', 'You received a new alert.', '/notifications/');
            } else if (currentMsgCount > lastMsgCount) {
                showLiveToast('New Message', 'A partner has sent you a direct message.', '/messages/');
            }

            lastNotifCount = currentNotifCount;
            lastMsgCount = currentMsgCount;

            // Update DOM badges
            refreshBadge('.icon-btn--bell', currentNotifCount);
            refreshBadge('.icon-btn--msg', currentMsgCount);
        })
        .catch(err => console.error('Count sync failed:', err));
}

function refreshBadge(selector, count) {
    const btn = document.querySelector(selector);
    if (!btn) return;

    let badge = btn.querySelector('.badge-count');
    if (count > 0) {
        btn.classList.add('has-new');
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'badge-count';
            btn.appendChild(badge);
        }
        badge.textContent = count;
    } else {
        btn.classList.remove('has-new');
        if (badge) badge.remove();
    }
}

function showLiveToast(title, text, link) {
    // Remove existing if any
    const existing = document.getElementById('live-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'live-toast';
    toast.className = 'toast-popup';
    toast.innerHTML = `
        <div class="toast-content" style="cursor: pointer;" onclick="window.location.href='${link}'">
            <h4>${title}</h4>
            <p>${text}</p>
        </div>
        <button onclick="this.parentElement.remove()" style="background:none; border:none; color:#666; cursor:pointer; font-weight:800; margin-left:10px;">×</button>
    `;
    document.body.appendChild(toast);

    // Auto remove after 8 seconds
    setTimeout(() => {
        if (toast.parentElement) toast.remove();
    }, 8000);
}

// Mark portal notifications as read via AJAX
function markPortalRead(msgId, element) {
    fetch(`/notification/${msgId}/read/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    }).then(res => res.json()).then(data => {
        if (data.status === 'ok') {
            if (element) {
                element.classList.add('is-read');
                // find the parent notif-item and dim it
                const item = element.closest('.notif-item');
                if (item) item.style.opacity = '0.7';
            }
            updateBadges(); // Refresh counts immediately
        }
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Initial update and periodic polling (every 15 seconds)
document.addEventListener('DOMContentLoaded', () => {
    updateBadges();
    setInterval(updateBadges, 10000);
});

