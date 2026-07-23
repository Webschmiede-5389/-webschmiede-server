import { useState, FormEvent } from "react";
import { Link } from "react-router-dom";
import { N8N, SLA } from "../lib/config";

export type TicketPriority = "critical" | "normal";

export interface SupportTicketPayload {
  subject: string;
  priority: TicketPriority;
  message: string;
  name: string;
  email: string;
  phone?: string;
  company?: string;
  source: string;
  submittedAt: string;
}

interface SupportTicketWidgetProps {
  compact?: boolean;
  onSuccess?: () => void;
}

const PRIORITY_LABELS: Record<TicketPriority, string> = {
  critical: "Kritisch – Systemausfall",
  normal: "Normal",
};

export function SupportTicketWidget({ compact = false, onSuccess }: SupportTicketWidgetProps) {
  const [subject, setSubject] = useState("");
  const [priority, setPriority] = useState<TicketPriority>("normal");
  const [message, setMessage] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [company, setCompany] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setErrorMsg("");

    const payload: SupportTicketPayload = {
      subject: subject.trim(),
      priority,
      message: message.trim(),
      name: name.trim(),
      email: email.trim(),
      phone: phone.trim() || undefined,
      company: company.trim() || undefined,
      source: "digitalehandwerkskunst-support",
      submittedAt: new Date().toISOString(),
    };

    try {
      const res = await fetch(N8N.supportWebhook, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        throw new Error(`Webhook antwortete mit ${res.status}`);
      }
      setStatus("ok");
      setSubject("");
      setMessage("");
      onSuccess?.();
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }

  return (
    <div className={compact ? "" : "card"}>
      {!compact && (
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-brand-ink">Support-Ticket</h2>
          <p className="mt-2 text-sm text-brand-muted">
            Beschreiben Sie Ihr Anliegen – wir melden uns zeitnah zurück.
          </p>
        </div>
      )}

      <div className="mb-6 rounded-xl border border-brand-orange/30 bg-brand-orange-soft p-4 text-sm text-brand-ink">
        <p className="font-semibold">SLA – unsere Spielregeln</p>
        <p className="mt-1 text-brand-muted">{SLA.note}</p>
        <p className="mt-2 text-xs text-brand-muted">
          Außerhalb der Geschäftszeiten bearbeiten wir kritische Störungen zum nächsten Werktag mit
          höchster Priorität.
        </p>
      </div>

      {status === "ok" ? (
        <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-sm text-green-800">
          Ticket eingegangen. Sie erhalten eine Bestätigung per E-Mail, sobald der Workflow
          verarbeitet wurde.
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="label" htmlFor="ticket-name">
                Name *
              </label>
              <input
                id="ticket-name"
                className="field"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="ticket-email">
                E-Mail *
              </label>
              <input
                id="ticket-email"
                type="email"
                className="field"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="label" htmlFor="ticket-company">
                Firma
              </label>
              <input
                id="ticket-company"
                className="field"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="ticket-phone">
                Telefon
              </label>
              <input
                id="ticket-phone"
                type="tel"
                className="field"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="label" htmlFor="ticket-subject">
              Betreff *
            </label>
            <input
              id="ticket-subject"
              className="field"
              required
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="z. B. Bestellportal offline"
            />
          </div>

          <div>
            <label className="label" htmlFor="ticket-priority">
              Priorität *
            </label>
            <select
              id="ticket-priority"
              className="field"
              value={priority}
              onChange={(e) => setPriority(e.target.value as TicketPriority)}
            >
              {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="label" htmlFor="ticket-message">
              Nachricht *
            </label>
            <textarea
              id="ticket-message"
              className="field min-h-[140px] resize-y"
              required
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Was ist passiert? Seit wann? Betroffene URL oder Dienst?"
            />
          </div>

          {status === "error" && (
            <p className="text-sm text-red-600" role="alert">
              Fehler beim Senden: {errorMsg}
            </p>
          )}

          <p className="text-xs text-brand-muted">
            Mit Absenden willigen Sie in die Verarbeitung Ihrer Angaben zur Bearbeitung des
            Support-Tickets ein. Details:{" "}
            <Link to="/datenschutz" className="text-brand-orange hover:underline">
              Datenschutzerklärung
            </Link>{" "}
            (Abschnitt 5).
          </p>

          <button type="submit" className="btn-primary w-full md:w-auto" disabled={status === "loading"}>
            {status === "loading" ? "Wird gesendet …" : "Ticket absenden"}
          </button>
        </form>
      )}
    </div>
  );
}
