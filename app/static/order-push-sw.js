/* Web Push für Gäste – Bestellportal (/bestellen) */
self.addEventListener("push", (event) => {
  let payload = { title: "Bestellung", body: "Neues Update zu deiner Bestellung", tag: "order", url: "/bestellen" };
  if (event.data) {
    try {
      payload = { ...payload, ...event.data.json() };
    } catch (e) {
      payload.body = event.data.text() || payload.body;
    }
  }
  const opts = {
    body: payload.body,
    icon: "/favicon-192.png",
    badge: "/favicon-192.png",
    tag: payload.tag || "order",
    data: { url: payload.url || "/bestellen" },
    requireInteraction: false,
  };
  event.waitUntil(self.registration.showNotification(payload.title || "Bestellung", opts));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/bestellen";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if (c.url.includes("/bestellen") && "focus" in c) return c.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
