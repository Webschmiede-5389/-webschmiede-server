import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { COMPANY } from "../lib/config";

const h2 = "mt-8 text-xl font-semibold text-brand-ink";
const h3 = "mt-4 text-lg font-medium text-brand-ink";

export default function DatenschutzPage() {
  return (
    <Layout>
      <article className="mx-auto max-w-3xl px-4 py-16 text-brand-muted">
        <h1 className="text-4xl font-bold text-brand-ink">Datenschutzerklärung</h1>
        <p className="mt-4">Stand: 22. Juli 2026</p>
        <p className="mt-2 text-sm">
          Diese Erklärung gilt für {COMPANY.siteUrl} (Webschmiede / Digitale Handwerkskunst).
          Kundenportale (z. B. Bestellseiten) haben ergänzende Hinweise beim jeweiligen Betrieb.
        </p>

        <h2 className={h2}>1. Verantwortlicher</h2>
        <p className="mt-2">
          {COMPANY.legalName}, {COMPANY.brandName}
          <br />
          {COMPANY.street}, {COMPANY.zipCity}
          <br />
          Telefon: {COMPANY.phone} · E-Mail: {COMPANY.email}
          <br />
          USt-IdNr.: {COMPANY.vatId}
        </p>

        <h2 className={h2}>2. Überblick</h2>
        <p className="mt-2">
          Wir verarbeiten personenbezogene Daten nur, soweit dies zur Bereitstellung unserer Website,
          zur Vertragsanbahnung und -durchführung sowie zur sicheren Betriebsführung erforderlich
          ist. Rechtsgrundlagen: Art. 6 Abs. 1 lit. a, b, c und f DSGVO.
        </p>
        <p className="mt-2 text-sm">
          Ein Verzeichnis von Verarbeitungstätigkeiten gemäß Art. 30 DSGVO führen wir intern.
        </p>

        <h2 className={h2}>3. Hosting bei Hetzner Online GmbH</h2>
        <p className="mt-2">
          Website, APIs, Automation und zugehörige Dienste werden auf Servern der{" "}
          <strong>Hetzner Online GmbH</strong> (Industriestr. 25, 91710 Gunzenhausen, Deutschland)
          betrieben. Dabei werden technische Zugriffsdaten verarbeitet (IP-Adresse, Zeitstempel,
          angeforderte URL, User-Agent). Rechtsgrundlage: Art. 6 Abs. 1 lit. f DSGVO. Mit Hetzner
          besteht ein Auftragsverarbeitungsvertrag gemäß Art. 28 DSGVO.
        </p>

        <h2 className={h2}>4. Server-Logdateien</h2>
        <p className="mt-2">
          Der Webserver (Nginx) speichert Zugriffsprotokolle zur Fehleranalyse und Abwehr von
          Angriffen. Logrotation: täglich, Aufbewahrung in der Regel 14 Tage, danach Löschung.
        </p>

        <h2 className={h2}>5. Kontakt, Support-Tickets und n8n-Webhooks</h2>
        <p className="mt-2">
          Bei Kontakt per Formular, E-Mail, Telefon oder Support-Ticket verarbeiten wir die von
          Ihnen angegebenen Daten (Name, E-Mail, Firma, Telefon, Betreff, Nachricht, Priorität,
          Zeitstempel) zur Bearbeitung der Anfrage.
        </p>
        <h3 className={h3}>n8n-Workflow-Automation</h3>
        <p className="mt-2">
          Support-Tickets und Automatisierungen werden über <strong>n8n</strong> (self-hosted auf
          unserem Hetzner-Server) verarbeitet. Formulardaten werden per HTTPS-Webhook an n8n
          übermittelt. Rechtsgrundlage: Art. 6 Abs. 1 lit. b (Vertragsanbahnung/-durchführung)
          bzw. lit. f (berechtigtes Interesse an zuverlässigem Support). n8n-Ausführungslogs werden
          nach max. 7 Tagen automatisch gelöscht.
        </p>
        <h3 className={h3}>Telegram-Benachrichtigung (intern)</h3>
        <p className="mt-2">
          Zur schnellen Bearbeitung kritischer Support-Anfragen leitet unser n8n-Workflow eine
          interne Benachrichtigung an <strong>Telegram</strong> (Telegram FZ-LLC, Dubai/VAE bzw.
          weltweite Server) weiter. Dabei können Name, E-Mail, Firma, Telefon, Betreff und
          Nachrichtentext in der Telegram-Nachricht enthalten sein. Rechtsgrundlage: Art. 6 Abs. 1
          lit. f DSGVO (zeitnahe Störungsbearbeitung). Telegram-Nachrichten werden von uns nach
          Erledigung des Tickets gelöscht; spätestens nach 90 Tagen. Es bestehen Standardvertragsklauseln
          (SCC) soweit erforderlich.
        </p>
        <h3 className={h3}>Agency Brain / interne CRM-Ablage</h3>
        <p className="mt-2">
          Support-Tickets können zusätzlich in unserem internen CRM (Agency Brain API auf dem
          Hetzner-Server) gespeichert werden, um Anfragen nachverfolgen zu können. Rechtsgrundlage:
          Art. 6 Abs. 1 lit. b bzw. lit. f DSGVO. Aufbewahrung: bis zur Erledigung, danach Archivierung
          max. 24 Monate, sofern keine gesetzlichen Aufbewahrungspflichten entgegenstehen.
        </p>

        <h2 className={h2}>6. Anfragen per E-Mail, WhatsApp und Formular</h2>
        <p className="mt-2">
          Preis- und Projektanfragen erfolgen per E-Mail, WhatsApp oder über das Support-Formular.
          Dabei verarbeiten wir die von Ihnen mitgeteilten Kontaktdaten und Nachrichteninhalte zur
          Bearbeitung der Anfrage. Rechtsgrundlage: Art. 6 Abs. 1 lit. b bzw. lit. f DSGVO.
        </p>

        <h2 className={h2}>7. Meta Pixel (Facebook/Instagram)</h2>
        <p className="mt-2">
          Sofern auf Kundenprojekten oder Kampagnen-Landingpages ein <strong>Meta Pixel</strong>{" "}
          eingesetzt wird, erfolgt dies nur nach vorheriger Einwilligung (Art. 6 Abs. 1 lit. a
          DSGVO). Der Pixel kann Daten an Meta Platforms Ireland Ltd. übermitteln. Auf der
          öffentlichen Agentur-Website ist standardmäßig kein Meta Pixel aktiv.
        </p>

        <h2 className={h2}>8. WhatsApp Business API</h2>
        <p className="mt-2">
          Bei gebuchten WhatsApp-Diensten verarbeiten wir Kontaktdaten und Nachrichteninhalte über
          die <strong>WhatsApp Business Cloud API</strong> (Meta). Rechtsgrundlage: Art. 6 Abs. 1
          lit. b DSGVO bzw. lit. a bei Erstkontakt. Eine Schaltfläche verlinkt zu WhatsApp – erst
          bei aktivem Klick entsteht eine Verbindung zu Meta.
        </p>

        <h2 className={h2}>9. DocuSeal – Vertragsunterzeichnung</h2>
        <p className="mt-2">
          Für digitale Vertragsunterzeichnung nutzen wir <strong>DocuSeal</strong> (self-hosted unter
          sign.digitalehandwerkskunst.de, Server in Deutschland). Verarbeitet werden Name, E-Mail,
          Vertragsdokumente, Signaturdaten und Zeitstempel. Rechtsgrundlage: Art. 6 Abs. 1 lit. b
          DSGVO. Mit DocuSeal besteht ein AVV gemäß Art. 28 DSGVO.
        </p>

        <h2 className={h2}>10. Schriftarten, CDN und Endgeräte-Speicher (TTDSG)</h2>
        <p className="mt-2">
          Schriftarten von <strong>Bunny Fonts</strong> (fonts.bunny.net, EU) und Icons von{" "}
          <strong>cdnjs</strong> (Cloudflare) werden erst nach Ihrer Einwilligung über den
          Hinweisbanner geladen. Dabei wird Ihre IP-Adresse an die Anbieter übermittelt.
          Rechtsgrundlage bei Einwilligung: Art. 6 Abs. 1 lit. a DSGVO und § 25 Abs. 1 TTDSG.
          Ohne Einwilligung („Nur notwendig“) nutzen wir System-Schriftarten Ihres Geräts; es
          erfolgt keine Verbindung zu Bunny/cdnjs. Ihre Wahl speichern wir lokal im Browser (
          <code className="text-xs">ws_cdn_consent</code>). Sie können die Einstellung im Footer
          unter „Cookie-/CDN-Einstellungen“ jederzeit zurücksetzen. Cloudflare: ggf.
          Standardvertragsklauseln bei Drittlandtransfer. Es werden keine Tracking-Cookies zu
          Marketingzwecken gesetzt.
        </p>

        <h2 className={h2}>11. Weitere Dienste (soweit gebucht)</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>Stripe – Zahlungsabwicklung (Art. 6 Abs. 1 lit. b DSGVO)</li>
          <li>seven.io – SMS-Benachrichtigungen</li>
          <li>Cal.com – Terminbuchung (self-hosted DE)</li>
        </ul>

        <h2 className={h2}>12. Markenlogos</h2>
        <p className="mt-2">
          Logos Dritter werden lokal von unserem Server ausgeliefert. Beim Seitenaufruf werden keine
          personenbezogenen Daten an die genannten Anbieter übermittelt.{" "}
          <Link to="/markenhinweise" className="text-brand-orange hover:underline">
            Markenhinweise
          </Link>
        </p>

        <h2 className={h2}>13. Speicherdauer (Übersicht)</h2>
        <ul className="mt-2 list-disc space-y-2 pl-5">
          <li>Server-Logs (Nginx): max. 14 Tage</li>
          <li>n8n-Ausführungslogs: max. 7 Tage</li>
          <li>Support-Tickets (CRM/intern): bis Erledigung, Archiv max. 24 Monate</li>
          <li>Telegram-Benachrichtigungen (Support): Löschung nach Erledigung, spätestens 90 Tage</li>
          <li>Kontakt-/Projektanfragen: bis Erledigung, Archiv max. 12 Monate</li>
          <li>Vertrags- und Rechnungsdaten: gesetzliche Aufbewahrungsfristen (in der Regel 6–10 Jahre)</li>
          <li>DocuSeal-Unterlagen: Vertragslaufzeit + gesetzliche Fristen; projektbezogene Kundendaten gemäß AVV binnen 30 Tagen nach Vertragsende</li>
        </ul>

        <h2 className={h2}>14. Ihre Rechte</h2>
        <p className="mt-2">
          Auskunft, Berichtigung, Löschung, Einschränkung, Datenübertragbarkeit, Widerspruch.
          Kontakt: {COMPANY.email}. Beschwerde: LDI NRW, www.ldi.nrw.de.
        </p>

        <h2 className={h2}>15. SSL/TLS</h2>
        <p className="mt-2">Diese Website nutzt TLS-Verschlüsselung.</p>

        <p className="mt-8 flex flex-wrap gap-4">
          <Link to="/impressum" className="text-brand-orange hover:underline">
            Impressum
          </Link>
          <Link to="/support" className="text-brand-orange hover:underline">
            Support
          </Link>
          <Link to="/" className="text-brand-orange hover:underline">
            Zurück zur Startseite
          </Link>
        </p>
      </article>
    </Layout>
  );
}
