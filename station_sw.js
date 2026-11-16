/* Keep the local station shell independent from the remote coordinator. */
const CACHE='displaycontrol-station-v1';
const SHELL=['/prompt_player.html','/prompt_shared.js','/branding.js','/favicon.svg','/connect.html','/player.html','/physical_boot.js'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(self.clients.claim());});
self.addEventListener('fetch',event=>{const url=new URL(event.request.url);if(event.request.method!=='GET'||url.origin!==location.origin||url.pathname.startsWith('/api/'))return;event.respondWith(fetch(event.request).catch(()=>caches.match(event.request)));});
