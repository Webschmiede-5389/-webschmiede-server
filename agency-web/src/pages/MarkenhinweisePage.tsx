import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";

export default function MarkenhinweisePage() {
  return (
    <Layout>
      <article className="mx-auto max-w-3xl px-4 py-16 text-brand-muted">
        <h1 className="text-4xl font-bold text-brand-ink">Marken- &amp; Kompatibilitätshinweise</h1>
        <p className="mt-2 text-sm">
          Stand: {new Date().getFullYear()} · Ergänzung zu{" "}
          <Link to="/impressum" className="text-brand-orange hover:underline">
            Impressum
          </Link>
        </p>

        <h2 className="mt-10 text-xl font-semibold text-brand-ink">Zweck der Übersicht</h2>
        <p>
          Auf unserer Website listen wir unter „Anbindungen“ Softwareprodukte und Dienste Dritter,
          die <strong className="text-brand-ink">typischerweise</strong> in unserer Zielgruppe
          (Gastronomie, Handwerk, KMU) eingesetzt werden. Die Darstellung dient ausschließlich der
          Information über technische Kompatibilität, nicht der Werbung für fremde Produkte
          und nicht der Darstellung einer geschäftlichen Verbindung zu deren Anbietern.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Keine Partnerschaft</h2>
        <p>
          Sofern auf dieser Website nicht ausdrücklich anders gekennzeichnet, besteht zwischen
          WebSchmiede · Digitale Handwerkskunst (Christian Kummetat) und den genannten
          Unternehmen <strong className="text-brand-ink">keine</strong> Partnerschaft, kein
          Vertrieb, keine Lizenz, kein Sponsoring, keine gemeinsame Marke und keine offizielle
          Zertifizierung. Die Nennung von Produktnamen und die Darstellung von Logos bedeutet
          nicht, dass der jeweilige Anbieter unsere Leistungen empfiehlt, prüft oder unterstützt.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Markenrechte</h2>
        <p>
          Alle genannten Produktnamen, Marken, Logos und Handelsnamen sind Eigentum der jeweiligen
          Rechteinhaber. Wir beanspruchen keine Rechte an diesen Marken. Die Verwendung erfolgt
          ausschließlich zur <strong className="text-brand-ink">identifizierenden Benennung</strong>{" "}
          kompatibler Systeme (sog. referierende / beschreibende Nutzung), soweit dies nach
          allgemeinen markenrechtlichen Grundsätzen zulässig ist.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Bedeutung der Status-Kennzeichnungen</h2>
        <ul className="mt-3 list-inside list-disc space-y-2">
          <li>
            <strong className="text-brand-ink">Im Einsatz bei WebSchmiede.</strong> Wir nutzen
            diese Technologie in unserem eigenen Betrieb oder für unsere Kundenprojekte, sofern beim
            jeweiligen Kunden freigegeben. Das bezieht sich auf <em>unsere</em> Nutzung, nicht auf
            eine Partnerschaft mit dem Anbieter.
          </li>
          <li>
            <strong className="text-brand-ink">Technisch anbindbar:</strong> Eine Anbindung ist
            grundsätzlich über öffentliche Schnittstellen (API), Webhooks oder Automatisierung möglich,
            sofern der Kunde die Voraussetzungen erfüllt (Account, Freigaben, Tarif). Es besteht keine
            Garantie, dass jede Funktion jedes Produkts angebunden werden kann.
          </li>
          <li>
            <strong className="text-brand-ink">Export / Schnittstelle:</strong> Datenaustausch über
            Exporte, Importe oder dokumentierte Partner-/Plattformwege des jeweiligen Anbieters,
            ohne dass WebSchmiede offizieller Plattformpartner ist.
          </li>
        </ul>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Wettbewerbsrecht (UWG)</h2>
        <p>
          Wir vermeiden irreführende Angaben im Sinne des Gesetzes gegen den unlauteren Wettbewerb (UWG).
          Insbesondere geben wir nicht vor, von Drittanbietern empfohlen, zertifiziert oder autorisiert zu
          sein, wenn dem nicht ausdrücklich so entsprochen wurde. Status-Kennzeichnungen auf der Website
          beschreiben <strong className="text-brand-ink">unseren</strong> technischen oder betrieblichen
          Stand, nicht den des jeweiligen Software-Herstellers.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Keine Zusicherung</h2>
        <p>
          Wir übernehmen keine Gewähr dafür, dass externe Dienste jederzeit verfügbar, API-fähig
          oder in einem bestimmten Tarif nutzbar sind. Änderungen durch Drittanbieter können
          Anbindungen beeinflussen. Konkrete Anbindungen werden im Einzelfall mit dem Kunden
          vertraglich vereinbart.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Hinweise &amp; Korrekturen</h2>
        <p>
          Sind Sie Markeninhaber und sehen die Darstellung als unzulässig an, kontaktieren Sie uns
          bitte unter{" "}
          <a href="mailto:info@digitalehandwerkskunst.de" className="text-brand-orange hover:underline">
            info@digitalehandwerkskunst.de
          </a>
          . Wir prüfen berechtigte Hinweise zeitnah und passen die Darstellung bei Bedarf an.
        </p>

        <p className="mt-10 rounded-xl border border-brand-border bg-brand-bg p-4 text-xs">
          Hinweis: Dieser Text ersetzt keine individuelle Rechtsberatung. Bei rechtlichen Fragen
          wenden Sie sich an einen Fachanwalt für Marken- oder Wettbewerbsrecht.
        </p>

        <p className="mt-8 flex flex-wrap gap-4">
          <Link to="/#integrationen" className="text-brand-orange hover:underline">
            ← Zur Anbindungs-Übersicht
          </Link>
          <Link to="/" className="text-brand-orange hover:underline">
            Startseite
          </Link>
        </p>
      </article>
    </Layout>
  );
}
