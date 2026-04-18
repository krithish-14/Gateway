(function() {
    // 1. Resolve User Identity for Persistence
    const getUserId = () => {
        if (window.CRM_USER_ID && window.CRM_USER_ID !== 'guest') return window.CRM_USER_ID;
        const match = document.cookie.match(/theme_user_id=([^;]+)/);
        return match ? match[1] : 'global';
    };

    const userId = getUserId();
    const storageKey = 'gateway-theme-' + userId;
    
    // 2. Theme Logic
    const getTheme = () => localStorage.getItem(storageKey) || 'light';
    
    const applyTheme = (theme) => {
        console.log('[Theme] Applying:', theme);
        document.documentElement.setAttribute('data-theme', theme);
        document.body.classList.remove('light-mode', 'dark-mode');
        document.body.classList.add(theme + '-mode');
        
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            const isDark = theme === 'dark';
            btn.style.background = isDark ? '#f59e0b' : '#3b82f6';
            btn.innerHTML = `<i class="fas fa-${isDark ? 'sun' : 'moon'}" style="color: white; font-size: 16px;"></i>`;
            btn.title = `Switch to ${isDark ? 'Light' : 'Dark'} Mode`;
        }
    };

    const toggleTheme = () => {
        const current = getTheme();
        const next = current === 'dark' ? 'light' : 'dark';
        localStorage.setItem(storageKey, next);
        applyTheme(next);
        return next;
    };

    // 3. Global Transitions (Self-Injecting)
    const injectStyles = () => {
        if (document.getElementById('gateway-theme-styles')) return;
        const style = document.createElement('style');
        style.id = 'gateway-theme-styles';
        style.innerHTML = `
            * { transition: background-color 0.4s ease, border-color 0.4s ease, color 0.4s ease !important; }
            .theme-toggle-btn { 
                transition: transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1), background 0.4s ease !important;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
            }
            .theme-toggle-btn:active { transform: scale(0.8) !important; }
            .theme-toggle-btn:hover { transform: scale(1.1); filter: brightness(1.1); }
        `;
        document.head.appendChild(style);
    };

    // 4. Initialization
    let rotation = 0;
    const init = () => {
        injectStyles();
        let btn = document.getElementById('theme-toggle');
        
        // If button is missing, DO NOT inject it automatically anymore
        // Only attach logic if it's already in the HTML (e.g., Home Page)
        if (!btn) {
            console.log('[Theme] No toggle button found on this page. Only reflecting preference.');
        } else {
            // Clean clone to prevent listener stacking
            const newBtn = btn.cloneNode(true);
            btn.parentNode.replaceChild(newBtn, btn);
            
            newBtn.addEventListener('click', () => {
                rotation += 360;
                newBtn.style.transform = `rotate(${rotation}deg)`;
                toggleTheme();
            });
        }
        
        applyTheme(getTheme());
    };

    // Run immediately for theme reflection
    document.documentElement.setAttribute('data-theme', getTheme());
    
    // Defer full init until DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Cross-tab sync
    window.addEventListener('storage', (e) => {
        if (e.key === storageKey) applyTheme(e.newValue);
    });

    // Expose helpers
    window.GatewayTheme = { toggle: toggleTheme, current: getTheme };
})();
