// Shared frontend helpers for the Local Cloud app with Keycloak integration
// Keep this file dependency-free and usable via a simple <script> include.
(function(global){
    // Keycloak configuration (loaded from backend)
    let keycloakConfig = null;
    let keycloak = null;

    // Token management
    function getToken(){ return sessionStorage.getItem('access_token') }
    function setToken(t){ if(t) sessionStorage.setItem('access_token', t) }
    function removeToken(){ sessionStorage.removeItem('access_token') }

    function headers(includeJson){
        const t = getToken();
        const h = {};
        if (t) h['Authorization'] = 'Bearer ' + t;
        if (includeJson) h['Content-Type'] = 'application/json';
        return h;
    }

    // Load Keycloak configuration from backend
    async function loadKeycloakConfig() {
        if (keycloakConfig) return keycloakConfig;
        try {
            const r = await fetch('/api/auth/config');
            if (!r.ok) throw new Error('Failed to load Keycloak config');
            keycloakConfig = await r.json();
            return keycloakConfig;
        } catch(e) {
            console.error('Failed to load Keycloak config:', e);
            return null;
        }
    }

    // Initialize Keycloak adapter
    async function initKeycloak() {
        if (keycloak) return keycloak;
        
        const config = await loadKeycloakConfig();
        if (!config) {
            console.error('Cannot initialize Keycloak without configuration');
            return null;
        }

        // Check if we have Keycloak JS library loaded
        if (typeof Keycloak === 'undefined') {
            console.error('Keycloak JS library not loaded');
            return null;
        }

        keycloak = new Keycloak({
            url: config.server_url,
            realm: config.realm,
            clientId: config.client_id
        });

        try {
            const authenticated = await keycloak.init({
                onLoad: 'check-sso',
                silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html',
                pkceMethod: 'S256'
            });

            if (authenticated) {
                setToken(keycloak.token);
                
                // Setup token refresh
                keycloak.onTokenExpired = () => {
                    keycloak.updateToken(30).then(refreshed => {
                        if (refreshed) {
                            setToken(keycloak.token);
                        }
                    }).catch(() => {
                        console.error('Failed to refresh token');
                        logout();
                    });
                };
            }

            return keycloak;
        } catch(e) {
            console.error('Failed to initialize Keycloak:', e);
            return null;
        }
    }

    // Login via Keycloak
    async function login() {
        const kc = await initKeycloak();
        if (kc) {
            kc.login();
        } else {
            alert('Authentication service unavailable. Please try again later.');
        }
    }

    // Logout via Keycloak
    async function logout() {
        removeToken();
        const kc = await initKeycloak();
        if (kc && kc.authenticated) {
            kc.logout();
        } else {
            // Fallback if Keycloak not available
            window.location.href = '/index.html';
        }
    }

    async function whoami(){
        try{
            const r = await fetch('/api/auth/whoami', { headers: headers() });
            if (!r.ok) return null;
            return await r.json();
        }catch(e){ return null }
    }

    function redirectToRole(me){
        if (!me) return;
        if (me.role === 'admin') location.href = '/admin.html';
        else if (me.role === 'moderator') location.href = '/moderator.html';
        else location.href = '/user.html';
    }

    async function downloadBlobResponse(res, fallbackName){
        if (!res.ok) { alert('Download failed: ' + res.status); return; }
        const blob = await res.blob();
        const cd = res.headers.get('content-disposition') || '';
        let filename = fallbackName || 'download';
        const m = /filename\*=UTF-8''([^;\n]+)/.exec(cd) || /filename=?"?([^";]+)"?/.exec(cd);
        if (m) filename = decodeURIComponent(m[1]);
        const urlObj = window.URL.createObjectURL(blob);
        const a = document.createElement('a'); 
        a.href = urlObj; 
        a.download = filename; 
        document.body.appendChild(a); 
        a.click(); 
        a.remove(); 
        window.URL.revokeObjectURL(urlObj);
    }

    // Theme management
    function initTheme() {
        const savedTheme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
    }

    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    }

    function createThemeToggle() {
        const button = document.createElement('button');
        button.className = 'theme-toggle';
        button.innerHTML = `
            <svg viewBox="0 0 24 24">
                <path d="M12 2.25a.75.75 0 01.75.75v2.25a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM7.5 12a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM18.894 6.166a.75.75 0 00-1.06-1.06l-1.591 1.59a.75.75 0 101.06 1.061l1.591-1.59zM21.75 12a.75.75 0 01-.75.75h-2.25a.75.75 0 010-1.5H21a.75.75 0 01.75.75zM17.834 18.894a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 10-1.061 1.06l1.59 1.591zM12 18a.75.75 0 01.75.75V21a.75.75 0 01-1.5 0v-2.25A.75.75 0 0112 18zM7.758 17.303a.75.75 0 00-1.061-1.06l-1.591 1.59a.75.75 0 001.06 1.061l1.591-1.59zM6 12a.75.75 0 01-.75.75H3a.75.75 0 010-1.5h2.25A.75.75 0 016 12zM6.697 7.757a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 00-1.061 1.06l1.59 1.591z"/>
            </svg>
        `;
        button.addEventListener('click', toggleTheme);
        return button;
    }

    // Initialize theme on load
    document.addEventListener('DOMContentLoaded', initTheme);

    // Unit management for quota display
    let displayUnit = 'MB'; // default

    function initUnit() {
        const savedUnit = localStorage.getItem('displayUnit') || 'MB';
        displayUnit = savedUnit;
    }

    function setDisplayUnit(unit) {
        displayUnit = unit;
        localStorage.setItem('displayUnit', unit);
    }

    function getDisplayUnit() {
        return displayUnit;
    }

    function createUnitSelector(onChange, id = 'unitSelector') {
        const select = document.createElement('select');
        select.id = id;
        select.className = 'unit-selector';
        select.innerHTML = `
            <option value="B">B</option>
            <option value="KB">KB</option>
            <option value="MB">MB</option>
            <option value="GB">GB</option>
            <option value="TB">TB</option>
        `;
        select.value = displayUnit;
        select.addEventListener('change', () => {
            setDisplayUnit(select.value);
            if (onChange) onChange(select.value);
        });
        return select;
    }

    // Initialize unit on load
    document.addEventListener('DOMContentLoaded', initUnit);

    // Utility functions for quota display and input
    function formatBytes(bytes, unit) {
        if (unit === undefined) unit = displayUnit;
        if (bytes === 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const unitIndex = units.indexOf(unit.toUpperCase());
        if (unitIndex === -1) return bytes + ' B'; // fallback
        const size = bytes / Math.pow(1024, unitIndex);
        return size.toFixed(2) + ' ' + units[unitIndex];
    }

    function parseBytes(value, unit = 'B') {
        const num = parseFloat(value);
        if (isNaN(num)) return 0;
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const unitIndex = units.indexOf(unit.toUpperCase());
        if (unitIndex === -1) return num; // assume bytes
        return Math.round(num * Math.pow(1024, unitIndex));
    }

    // Expose helpers
    global.appCommon = {
        getToken, setToken, removeToken, headers, whoami, redirectToRole, downloadBlobResponse,
        createThemeToggle, formatBytes, parseBytes, createUnitSelector, getDisplayUnit, setDisplayUnit,
        login, logout, initKeycloak, loadKeycloakConfig
    };
})(window);