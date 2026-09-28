// YKS Sistemim - bildirim yardımcısı (github.html ile aynı klasörde durmalı)
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const tab = event.notification.data && event.notification.data.tab;
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ('focus' in client) {
          client.postMessage({ type: 'goto-tab', tab });
          return client.focus();
        }
      }
      return self.clients.openWindow('./');
    })
  );
});
