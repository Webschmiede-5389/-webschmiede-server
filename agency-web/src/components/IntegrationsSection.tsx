import { useState } from "react";
import { Link } from "react-router-dom";
import {
  INTEGRATION_CATEGORIES,
  STATUS_STYLES,
  type IntegrationTool,
} from "../data/integrations";
import { BOOKING } from "../lib/config";

function Logo({ tool }: { tool: IntegrationTool }) {
  const [failed, setFailed] = useState(false);
  const initial = tool.name.replace(/[^A-Za-z0-9]/g, "").slice(0, 2).toUpperCase();

  if (failed) {
    return (
      <div
        className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-brand-border bg-brand-bg text-xs font-bold text-brand-orange"
        title={tool.name}
        aria-hidden
      >
        {initial}
      </div>
    );
  }

  return (
    <img
      src={tool.logo}
      alt=""
      aria-hidden
      className="h-12 w-12 shrink-0 rounded-xl border border-brand-border bg-white object-contain p-1.5"
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

/** Kurzer Teaser für die Startseite – volle Liste unter /anbindungen */
export function IntegrationsTeaser() {
  const preview = INTEGRATION_CATEGORIES.flatMap((c) => c.tools).slice(0, 8);

  return (
    <section id="integrationen" className="border-b border-brand-border bg-white py-14 md:py-16">
      <div className="mx-auto max-w-6xl px-4 text-center">
        <p className="section-label">Anbindungen</p>
        <h2 className="section-title mt-2">Was viele Betriebe schon nutzen</h2>
        <p className="mx-auto mt-3 max-w-xl text-brand-muted">
          Lexware, DATEV, Kasse, WhatsApp und Co. Keine Partnerschaft mit den Herstellern. Ob es bei
          Ihnen passt, klären wir im Einzelfall.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          {preview.map((tool) => (
            <div
              key={tool.id}
              className="flex items-center gap-2 rounded-xl border border-brand-border bg-brand-bg px-3 py-2 text-sm font-medium text-brand-ink"
              title={tool.name}
            >
              <Logo tool={tool} />
              <span className="hidden sm:inline">{tool.name}</span>
            </div>
          ))}
        </div>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link to="/anbindungen" className="btn-outline text-sm">
            Alle Anbindungen ansehen
          </Link>
        </div>
      </div>
    </section>
  );
}

export function IntegrationsSection() {
  return (
    <section id="integrationen-full" className="border-y border-brand-border bg-brand-bg py-16 md:py-20">
      <div className="mx-auto max-w-6xl px-4">
        <div className="mx-auto max-w-3xl text-center">
          <p className="section-label">Kompatibilität</p>
          <h2 className="section-title mt-2">Software, die Betriebe oft schon nutzen</h2>
          <p className="mt-4 text-brand-muted">
            Übersicht typischer Systeme, technische Anbindung im Einzelfall, keine Partnerschaft
            mit den Anbietern. Wir ersetzen bestehende Tools nicht, wir verbinden sie sinnvoll.
          </p>
        </div>

        <div className="mt-8 flex flex-wrap justify-center gap-3 text-xs">
          {(["live", "api", "export"] as const).map((s) => (
            <span
              key={s}
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 font-medium ${STATUS_STYLES[s].pill}`}
              title="Legende, keine Partnerschaft mit den Anbietern"
            >
              <span className="h-2 w-2 rounded-full bg-current opacity-60" />
              {STATUS_STYLES[s].label}
            </span>
          ))}
        </div>

        <div className="mt-12 space-y-12">
          {INTEGRATION_CATEGORIES.map((cat) => (
            <div key={cat.id}>
              <h3 className="flex items-center gap-2 text-lg font-bold text-brand-ink">
                <i className={`fas ${cat.icon} text-brand-orange`} aria-hidden />
                {cat.label}
              </h3>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {cat.tools.map((tool) => (
                  <div
                    key={tool.id}
                    className="flex items-start gap-3 rounded-xl border border-brand-border bg-white p-4 shadow-sm transition hover:border-brand-orange/40 hover:shadow-md"
                    title={`${tool.name}, Marke des jeweiligen Anbieters; keine Partnerschaft.`}
                  >
                    <Logo tool={tool} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-brand-ink">{tool.name}</p>
                        <span
                          className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${STATUS_STYLES[tool.status].pill}`}
                        >
                          {tool.statusLabel}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-brand-muted">{tool.blurb}</p>
                      <p className="mt-2 text-[10px] text-brand-muted/80">
                        {tool.branches.join(" · ")}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <aside className="mx-auto mt-10 max-w-3xl rounded-xl border border-brand-border bg-white p-5 text-xs leading-relaxed text-brand-muted">
          <p className="font-semibold text-brand-ink">Rechtlicher Hinweis (Marken &amp; Kompatibilität)</p>
          <p className="mt-2">
            Produktnamen und Logos sind Marken der jeweiligen Rechteinhaber. Die Auflistung dient
            ausschließlich der Information über{" "}
            <strong className="font-medium text-brand-ink">mögliche technische Kompatibilität</strong>
            . Es besteht keine Partnerschaft, kein Sponsoring und keine offizielle Zertifizierung
            durch die genannten Anbieter, sofern nicht ausdrücklich anders gekennzeichnet.
          </p>
          <p className="mt-2">
            <Link to="/markenhinweise" className="text-brand-orange hover:underline">
              Ausführliche Markenhinweise
            </Link>
            {" · "}
            <Link to="/impressum" className="text-brand-orange hover:underline">
              Impressum
            </Link>
          </p>
        </aside>

        <div className="mt-10 flex justify-center">
          <a href={BOOKING.url} target="_blank" rel="noreferrer" className="btn-primary">
            {BOOKING.label}
          </a>
        </div>
      </div>
    </section>
  );
}
