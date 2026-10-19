const CACHE_NAME="cosmo-5.0-jarvis-default-shell";
const APP_SHELL=["/","/manifest.json","/static/fundo-cosmo.jpg","/static/logo-cosmo-transparent.png","/static/cosmo-cinematic-hud-v4.css","/static/cosmo-cinematic-hud-v4.js"];

self.addEventListener("install",event=>{
  event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(APP_SHELL)).then(()=>self.skipWaiting()));
});

self.addEventListener("activate",event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE_NAME).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));
});

self.addEventListener("fetch",event=>{
  const request=event.request;
  if(request.method!=="GET") return;
  event.respondWith(
    fetch(request).then(response=>{
      const clone=response.clone();
      caches.open(CACHE_NAME).then(cache=>cache.put(request,clone)).catch(()=>{});
      return response;
    }).catch(()=>caches.match(request).then(cached=>cached||caches.match("/")))
  );
});
