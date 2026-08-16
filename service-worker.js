const CACHE='sta-tratte-v1';
const ASSETS=['./','./index.html','./manifest.webmanifest'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET') return;
  event.respondWith(caches.match(event.request).then(cached=>cached || fetch(event.request).then(r=>{
    const copy=r.clone(); caches.open(CACHE).then(c=>c.put(event.request,copy)); return r;
  }).catch(()=>cached)));
});
