const CACHE='leafread-shell-v8';
const SHELL=['/','/style.css','/reader.css','/common.js','/app.js','/accounts.js','/library.js','/offline.js','/manifest.json','/import.js'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{const url=new URL(e.request.url);if(e.request.method!=='GET'||url.origin!==location.origin||url.pathname.startsWith('/api/'))return;e.respondWith(fetch(e.request).then(response=>{if(response.ok)caches.open(CACHE).then(c=>c.put(e.request,response.clone()));return response;}).catch(()=>caches.match(e.request)));});
