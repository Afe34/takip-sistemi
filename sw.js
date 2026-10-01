// YKS Sistemim - çevrimdışı çalışma + bildirim tıklama
const CACHE = 'yks-v1';
const SHELL = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png'];
const HOSTS = ['cdn.jsdelivr.net', 'www.gstatic.com'];   // Chart.js, confetti, Firebase modülleri

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => Promise.all(SHELL.map(u => c.add(u).catch(() => {})))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const ok = url.origin === self.location.origin || HOSTS.includes(url.hostname);
  if (!ok) return;   // Firestore/Auth istekleri SDK'ya bırakılır

  if (req.mode === 'navigate') {   // sayfa: önce ağ, internet yoksa önbellek
    e.respondWith(fetch(req).then(res => {
      const copy = res.clone(); caches.open(CACHE).then(c => c.put('./index.html', copy)); return res;
    }).catch(() => caches.match('./index.html').then(r => r || caches.match('./'))));
    return;
  }
  e.respondWith(caches.match(req).then(cached => {   // diğerleri: önbellek + arka planda yenile
    const net = fetch(req).then(res => {
      if (res && (res.status === 200 || res.type === 'opaque')) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    }).catch(() => cached);
    return cached || net;
  }));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const tab = (e.notification.data || {}).tab;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    for (const c of list) {
      if ('focus' in c) { c.focus(); if (tab) c.postMessage({ type: 'goto-tab', tab }); return; }
    }
    return self.clients.openWindow(tab ? './?tab=' + encodeURIComponent(tab) : './');
  }));
});
