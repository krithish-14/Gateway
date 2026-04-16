(function() {
    const getUserId = (name) => {
        if (window.CRM_USER_ID && window.CRM_USER_ID !== 'guest') return window.CRM_USER_ID;
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return 'guest';
    };

    const userId = getUserId('theme_user_id');
    const storageKey = 'theme-preference-' + userId;
    console.log('[Theme] Initializing for User:', userId, 'Storage Key:', storageKey);

    // Cleanup legacy global keys to prevent interference
    if (localStorage.getItem('theme-preference')) {
        console.log('[Theme] Cleaning up legacy global theme-preference key');
        localStorage.removeItem('theme-preference');
    }
    if (localStorage.getItem('theme')) {
        console.log('[Theme] Cleaning up legacy global theme key');
        localStorage.removeItem('theme');
    }

    const getColorPreference = () => {
        const saved = localStorage.getItem(storageKey);
        if (saved) {
            return saved;
        }
        return 'light';
    };

    const reflectPreference = () => {
        const theme = getColorPreference();
        console.log('[Theme] Applying preference:', theme, 'from key:', storageKey);
        document.documentElement.setAttribute('data-theme', theme);
        document.body.classList.remove('light-mode', 'dark-mode');
        document.body.classList.add(theme + '-mode');
        
        updateToggleIcon(theme);
    };

    const setPreference = (theme) => {
        console.log('[Theme] Setting preference:', theme);
        localStorage.setItem(storageKey, theme);
        reflectPreference();
    };

    const updateToggleIcon = (theme) => {
        const btn = document.getElementById('theme-toggle');
        if (!btn) return;
        
        if (theme === 'dark') {
            btn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #fbbf24;"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>';
        } else {
            btn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #64748b;"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>';
        }
    };

    const initToggle = () => {
        if (document.getElementById('theme-toggle')) return;

        let navIcons = document.querySelector('.nav-icons');
        if (!navIcons) {
            const navbar = document.querySelector('.navbar');
            if (!navbar) return;
            navIcons = document.createElement('div');
            navIcons.className = 'nav-icons';
            navIcons.style.display = 'flex';
            navIcons.style.alignItems = 'center';
            navIcons.style.gap = '15px';
            navIcons.style.marginLeft = 'auto';
            navbar.appendChild(navIcons);
        }

        const toggleBtn = document.createElement('button');
        toggleBtn.id = 'theme-toggle';
        toggleBtn.className = 'icon-btn theme-toggle-btn';
        toggleBtn.title = 'Switch Light/Dark Mode';
        toggleBtn.type = 'button';
        toggleBtn.style.background = 'rgba(128,128,128,0.1)';
        toggleBtn.style.border = 'none';
        toggleBtn.style.borderRadius = '50%';
        toggleBtn.style.width = '40px';
        toggleBtn.style.height = '40px';
        toggleBtn.style.display = 'flex';
        toggleBtn.style.alignItems = 'center';
        toggleBtn.style.justifyContent = 'center';
        toggleBtn.style.cursor = 'pointer';
        
        toggleBtn.addEventListener('click', () => {
            const current = getColorPreference();
            setPreference(current === 'dark' ? 'light' : 'dark');
        });

        navIcons.insertBefore(toggleBtn, navIcons.firstChild);
        updateToggleIcon(getColorPreference());
        console.log('[Theme] Toggle button initialized');
    };

    // Apply preference immediately
    reflectPreference();

    // Re-check and init on load
    if (document.readyState === 'loading') {
        window.addEventListener('DOMContentLoaded', () => {
            reflectPreference();
            initToggle();
        });
    } else {
        reflectPreference();
        initToggle();
    }

    // Expose to window
    window.setPreference = setPreference;
    window.getColorPreference = getColorPreference;
    window.reflectPreference = reflectPreference;
})();
