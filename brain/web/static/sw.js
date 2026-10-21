// BRAIN necesita la conexión con tu casa para funcionar: este "service worker"
// solo existe para que el móvil permita instalar BRAIN como aplicación.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
