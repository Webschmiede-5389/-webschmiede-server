/** TTDSG: externe Fonts/CDN erst nach Einwilligung laden. */

export const CONSENT_KEY = "ws_cdn_consent";
export type ConsentValue = "accepted" | "essential";

export const CDN_LINKS = [
  {
    id: "ws-bunny-fonts",
    rel: "stylesheet",
    href: "https://fonts.bunny.net/css?family=inter:400,500,600,700&display=swap",
  },
  {
    id: "ws-font-awesome",
    rel: "stylesheet",
    href: "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css",
    crossOrigin: "anonymous",
  },
] as const;

export function getConsent(): ConsentValue | null {
  try {
    const v = localStorage.getItem(CONSENT_KEY);
    if (v === "accepted" || v === "essential") return v;
  } catch {
    /* private mode */
  }
  return null;
}

export function setConsent(value: ConsentValue): void {
  try {
    localStorage.setItem(CONSENT_KEY, value);
  } catch {
    /* ignore */
  }
}

export function loadExternalCdn(): void {
  if (typeof document === "undefined") return;

  const preconnect = document.getElementById("ws-preconnect-bunny");
  if (!preconnect) {
    const link = document.createElement("link");
    link.id = "ws-preconnect-bunny";
    link.rel = "preconnect";
    link.href = "https://fonts.bunny.net";
    document.head.appendChild(link);
  }

  for (const item of CDN_LINKS) {
    if (document.getElementById(item.id)) continue;
    const el = document.createElement("link");
    el.id = item.id;
    el.rel = item.rel;
    el.href = item.href;
    if ("crossOrigin" in item && item.crossOrigin) {
      el.crossOrigin = item.crossOrigin;
    }
    document.head.appendChild(el);
  }

  document.documentElement.classList.add("cdn-loaded");
  document.documentElement.classList.remove("cdn-essential");
}

export function applyEssentialMode(): void {
  document.documentElement.classList.add("cdn-essential");
  document.documentElement.classList.remove("cdn-loaded");
}

export function applyStoredConsent(): ConsentValue | null {
  const stored = getConsent();
  if (stored === "accepted") loadExternalCdn();
  else if (stored === "essential") applyEssentialMode();
  return stored;
}
