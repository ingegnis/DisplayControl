/* Restricted transport shared by browser player and the offline Android shell. */
'use strict';
window.CARISMA_PHYSICAL = true;
(() => {
  const original = window.fetch.bind(window);
  const pending = new Map();
  let serial = 0;
  const native = window.CarismaDevice;
  function mapPath(value) {
    const u = new URL(value, location.href);
    if (u.origin !== location.origin || u.search || u.hash) throw Error('Solo API locali del player.');
    const path = u.pathname;
    if (path.startsWith('/api/player/')) return path;
    if (path === '/api/state') return '/api/player/state';
    if (path === '/api/preview') return '/api/player/preview';
    if (path === '/api/heartbeat') return '/api/player/heartbeat';
    if (path.startsWith('/api/assets/')) return path.replace('/api/assets/', '/api/player/assets/');
    if (path.startsWith('/api/ndi/')) return path.replace('/api/ndi/', '/api/player/ndi/');
    throw Error('API non consentita al player.');
  }
  window.CarismaNativeResult = (id, status, body) => {
    const p = pending.get(id);
    if (!p) return;
    p.cleanup();
    p.resolve(new Response(body, {status, headers:{'Content-Type':'application/json'}}));
  };
  window.fetch = async (url, opts={}) => {
    const path = mapPath(String(url));
    const method = (opts.method || 'GET').toUpperCase();
    if (!['GET', 'HEAD', 'POST'].includes(method)) throw Error('Player in sola lettura.');
    if (native && method === 'POST') {
      return new Promise((resolve, reject) => {
        const id = String(++serial);
        const cleanup = () => { clearTimeout(timer); pending.delete(id); opts.signal?.removeEventListener('abort', abort); };
        const abort = () => { cleanup(); reject(new DOMException('Richiesta interrotta', 'AbortError')); };
        const timer = setTimeout(abort, 20000);
        pending.set(id,{resolve,cleanup});
        if (opts.signal?.aborted) { abort(); return; }
        opts.signal?.addEventListener('abort', abort, {once:true});
        try { native.request(id, path, String(opts.body || '{}')); } catch (e) {cleanup(); reject(e);}
      });
    }
    const headers = new Headers(opts.headers || {});
    headers.delete('X-Control-Token');
    if (!native) headers.set('X-Player-Token', localStorage.getItem('carisma-device-token') || '');
    return original(path, {...opts, method, headers});
  };
  window.CarismaPlayerTransport = {mapPath};
})();
