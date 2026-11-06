// BRAIN needs the connection to your home to work: this "service worker"
// only exists so the phone allows installing BRAIN as an app.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
