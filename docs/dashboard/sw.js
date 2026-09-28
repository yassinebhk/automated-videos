// Service worker mínimo — hace la app "installable" en Chrome (criterio PWA).
// Estrategia: NETWORK-FIRST para data.json (datos frescos siempre) + CACHE
// FALLBACK para la shell HTML/iconos si no hay red. Ligero, sin librerías.
//
// Versionado: bump CACHE_NAME cuando cambies la shell → SW invalida caché vieja.
const CACHE_NAME = "cm-shell-v1";
const SHELL = [
  "./",
  "./index.html",
  "./icon-192.png",
  "./icon-512.png",
  "./manifest.webmanifest",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((c) => c.addAll(SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  // Purga cachés viejas
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  // Solo GET (POST/otros no se cachean)
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // data.json: NETWORK-FIRST (queremos datos frescos) con fallback caché
  if (url.pathname.endsWith("/data.json")) {
    e.respondWith(
      fetch(req)
        .then((res) => {
          // Cachea copia para offline
          const copy = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(req, copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Shell (HTML/iconos/manifest): CACHE-FIRST con actualización en segundo plano
  if (SHELL.some((p) => url.pathname.endsWith(p.replace("./", "/")) || url.pathname.endsWith(p.replace("./", "")))) {
    e.respondWith(
      caches.match(req).then((cached) => {
        const fetchPromise = fetch(req).then((res) => {
          caches.open(CACHE_NAME).then((c) => c.put(req, res.clone())).catch(() => {});
          return res;
        }).catch(() => cached);
        return cached || fetchPromise;
      })
    );
  }
  // Resto (Chart.js CDN, fuentes Google): default network (con caché HTTP del browser)
});
