// Shared frontend helpers for the Local Cloud app
// Keep this file dependency-free and usable via a simple <script> include.
(function(global){
    // In-memory token storage (no localStorage)
    // let accessToken = null;

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

    // Expose helpers
    global.appCommon = {
        getToken, setToken, removeToken, headers, whoami, redirectToRole, downloadBlobResponse
    };
})(window);