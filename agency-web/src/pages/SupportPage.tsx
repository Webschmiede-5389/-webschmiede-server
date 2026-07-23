import { Link } from "react-router-dom";
import { Layout, BOOKING } from "../components/Layout";
import { SupportTicketWidget } from "../components/SupportTicketWidget";

export default function SupportPage() {
  return (
    <Layout>
      <div className="mx-auto max-w-2xl px-4 py-16">
        <p className="section-label">Kundenportal</p>
        <h1 className="section-title mt-2">Support & Tickets</h1>
        <p className="mt-2 text-brand-muted">
          Für bestehende Kunden: Störungen melden, Priorität wählen, SLA einsehen.
        </p>
        <div className="mt-8">
          <SupportTicketWidget />
        </div>
        <p className="mt-8 text-sm text-brand-muted">
          Noch kein Kunde?{" "}
          <a
            href={BOOKING.url}
            target="_blank"
            rel="noreferrer"
            className="font-semibold text-brand-orange hover:underline"
          >
            {BOOKING.label}
          </a>
        </p>
        <p className="mt-4 text-sm text-brand-muted">
          <Link to="/" className="text-brand-orange hover:underline">
            ← Zurück zur Startseite
          </Link>
        </p>
      </div>
    </Layout>
  );
}
