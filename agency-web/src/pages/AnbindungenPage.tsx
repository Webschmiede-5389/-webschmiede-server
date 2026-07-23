import { Link } from "react-router-dom";
import { Layout, BOOKING } from "../components/Layout";
import { IntegrationsSection } from "../components/IntegrationsSection";

export default function AnbindungenPage() {
  return (
    <Layout>
      <div className="border-b border-brand-border bg-white px-4 py-10">
        <div className="mx-auto max-w-6xl">
          <p className="section-label">Anbindungen</p>
          <h1 className="section-title mt-2">Tools & Kompatibilität</h1>
          <p className="mt-3 max-w-2xl text-brand-muted">
            Übersicht typischer Systeme. Keine Partnerschaft mit den Anbietern – Anbindung im
            Einzelfall.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a href={BOOKING.url} target="_blank" rel="noreferrer" className="btn-primary text-sm">
              {BOOKING.label}
            </a>
            <Link to="/" className="btn-outline text-sm">
              ← Zur Startseite
            </Link>
          </div>
        </div>
      </div>
      <IntegrationsSection />
    </Layout>
  );
}
