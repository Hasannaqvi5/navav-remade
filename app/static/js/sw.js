// ── NavAv Service Worker ────────────────────────────────────────────────────────
// This script runs in the background, even when the web app is closed.
// It is responsible for listening for 'push' events from the server and
// displaying them as system-level notifications.

self.addEventListener('push', function(event) {
  // 1. Check if the push event contains data
  if (event.data) {
    const data = event.data.json();
    
    // 2. Configure the look and feel of the notification
    const options = {
      body: data.body,
      icon: '/static/icon-192.png',
      badge: '/static/icon-192.png',
      vibrate: [100, 50, 100],
      data: {
        url: data.url || '/' // Attach the URL for redirection on click
      },
      actions: [
        { action: 'open', title: 'View Details' },
        { action: 'close', title: 'Dismiss' }
      ]
    };

    // 3. Keep the service worker alive until the notification is shown
    event.waitUntil(
      self.registration.showNotification(data.title || 'NavAv Alert', options)
    );
  }
});

self.addEventListener('notificationclick', function(event) {
  // 1. Close the notification drawer immediately
  event.notification.close();

  // 2. If 'Dismiss' was clicked, do nothing
  if (event.action === 'close') return;

  // 3. Resolve the full destination URL
  const urlToOpen = new URL(event.notification.data.url, self.location.origin).href;

  // 4. Find an existing window/tab for the URL, or open a new one
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(windowClients) {
      // If a tab is already open to this page, just focus it
      for (let i = 0; i < windowClients.length; i++) {
        let client = windowClients[i];
        if (client.url === urlToOpen && 'focus' in client) {
          return client.focus();
        }
      }
      // Otherwise, open a fresh window
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});
