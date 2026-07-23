import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  applyEssentialMode,
  applyStoredConsent,
  getConsent,
  loadExternalCdn,
  setConsent,
  type ConsentValue,
} from "../lib/consent";

export function ConsentBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const stored = applyStoredConsent();
    setVisible(stored === null);
  }, []);

  function choose(value: ConsentValue) {
    setConsent(value);
    if (value === "accepted") loadExternalCdn();
    else applyEssentialMode();
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-labelledby="consent-title"
      aria-describedby="consent-desc"
      className="fixed inset-x-0 bottom-0 z-[100] border-t border-brand-border bg-white p-4 shadow-[0_-8px_32px_rgba(0,0,0,.08)] sm:p-5"
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 flex-1">
          <p id="consent-title" className="text-sm font-semibold text-brand-ink">
            Externe Inhalte (Schriftarten &amp; Icons)
          </p>
          <p id="consent-desc" className="mt-1 text-xs leading-relaxed text-brand-muted sm:text-sm">
            Zur einheitlichen Darstellung laden wir Schriftarten von Bunny Fonts (EU) und Icons
            von cdnjs/Cloudflare. Dabei wird Ihre IP-Adresse an diese Anbieter übermittelt. Ohne
            Einwilligung nutzen wir System-Schriftarten.{" "}
            <Link to="/datenschutz" className="text-brand-orange hover:underline">
              Datenschutz
            </Link>
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center">
          <button
            type="button"
            className="btn-outline text-sm"
            onClick={() => choose("essential")}
          >
            Nur notwendig
          </button>
          <button
            type="button"
            className="btn-primary text-sm"
            onClick={() => choose("accepted")}
          >
            Akzeptieren
          </button>
        </div>
      </div>
    </div>
  );
}

/** Footer-Link: Einwilligung zurücksetzen und Banner erneut zeigen. */
export function ConsentResetLink({ className = "" }: { className?: string }) {
  return (
    <button
      type="button"
      className={className}
      onClick={() => {
        try {
          localStorage.removeItem("ws_cdn_consent");
        } catch {
          /* ignore */
        }
        window.location.reload();
      }}
    >
      Cookie-/CDN-Einstellungen
    </button>
  );
}

export function hasCdnConsent(): boolean {
  return getConsent() === "accepted";
}
