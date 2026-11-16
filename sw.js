/* Cache the shell; media/manifests use IndexedDB.
 * Service workers need localhost/HTTPS; plain LAN HTTP cold-start is unverified.
 */
const CACHE = 'carisma-shell-v09';
const SHELL = ['./index.html','./favicon.svg','./branding.js','./prompt_shared.js',
  './prompt.html','./prompt_player.html','./monitor.html','./players.html',
  './connect.html','./player.html','./physical_boot.js'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('carisma-shell-') && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.match(url.pathname === '/' ? './index.html' : event.request,{ignoreSearch:true})));
  } else if (SHELL.some(path => url.pathname === new URL(path,self.location.href).pathname)) {
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request,{ignoreSearch:true})));
  }
});
