import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { COMPANY } from "../lib/config";

export default function ImpressumPage() {
  return (
    <Layout>
      <article className="mx-auto max-w-3xl px-4 py-16 text-brand-muted">
        <h1 className="text-4xl font-bold text-brand-ink">Impressum</h1>
        <p className="mt-2">Angaben gemäß § 5 DDG (Digitale-Dienste-Gesetz)</p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Diensteanbieter</h2>
        <p className="mt-2">
          {COMPANY.legalName}
          <br />
          handelnd unter „{COMPANY.brandName}“
          <br />
          {COMPANY.street}
          <br />
          {COMPANY.zipCity}
          <br />
          {COMPANY.country}
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Kontakt</h2>
        <p className="mt-2">
          Telefon: <a href={COMPANY.phoneLink}>{COMPANY.phone}</a>
          <br />
          E-Mail: <a href={`mailto:${COMPANY.email}`}>{COMPANY.email}</a>
          <br />
          Website: <a href={COMPANY.siteUrl}>{COMPANY.siteUrl.replace(/^https?:\/\//, "")}</a>
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Unternehmensform</h2>
        <p className="mt-2">
          Einzelunternehmen · Tätigkeit: Webdesign, digitale Dienstleistungen und Automation für
          Gewerbetreibende (B2B). Keine gesetzliche Berufszulassung, keine kammerpflichtige
          Berufsordnung.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Umsatzsteuer-ID</h2>
        <p className="mt-2">
          Umsatzsteuer-Identifikationsnummer gemäß § 27 a UStG: {COMPANY.vatId}
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">
          Verantwortlich für den Inhalt (§ 18 Abs. 2 MStV)
        </h2>
        <p className="mt-2">
          {COMPANY.legalName}, {COMPANY.street}, {COMPANY.zipCity}
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Streitbeilegung (§ 36 VSBG)</h2>
        <p className="mt-2">
          Die EU-Kommission stellt eine Plattform zur Online-Streitbeilegung bereit:{" "}
          <a href="https://ec.europa.eu/consumers/odr" target="_blank" rel="noreferrer">
            https://ec.europa.eu/consumers/odr
          </a>
          . Wir sind nicht verpflichtet und nicht bereit, an Streitbeilegungsverfahren vor einer
          Verbraucherschlichtungsstelle teilzunehmen, da wir ausschließlich mit Gewerbetreibenden
          kontrahieren.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Haftung für Inhalte (§ 5 DDG)</h2>
        <p className="mt-2">
          Als Diensteanbieter sind wir für eigene Inhalte auf diesen Seiten nach den allgemeinen
          Gesetzen verantwortlich. Wir sind nicht verpflichtet, übermittelte oder gespeicherte
          fremde Informationen zu überwachen oder nach Umständen zu forschen, die auf eine
          rechtswidrige Tätigkeit hinweisen. Verpflichtungen zur Entfernung oder Sperrung der
          Nutzung von Informationen nach den allgemeinen Gesetzen bleiben unberührt.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Haftung für Links</h2>
        <p className="mt-2">
          Unser Angebot enthält Links zu externen Websites Dritter, auf deren Inhalte wir keinen
          Einfluss haben. Für die Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter
          verantwortlich. Bei Bekanntwerden von Rechtsverletzungen entfernen wir derartige Links
          umgehend.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Urheberrecht</h2>
        <p className="mt-2">
          Die durch den Seitenbetreiber erstellten Inhalte und Werke auf diesen Seiten unterliegen
          dem deutschen Urheberrecht.
        </p>

        <h2 className="mt-8 text-xl font-semibold text-brand-ink">Marken &amp; Fremdnamen</h2>
        <p className="mt-2">
          Produktnamen und Logos Dritter sind Eigentum der jeweiligen Rechteinhaber.{" "}
          <Link to="/markenhinweise" className="text-brand-orange hover:underline">
            Markenhinweise
          </Link>
        </p>

        <p className="mt-8 flex flex-wrap gap-4">
          <Link to="/datenschutz" className="text-brand-orange hover:underline">
            Datenschutz
          </Link>
          <Link to="/support" className="text-brand-orange hover:underline">
            Support
          </Link>
          <Link to="/" className="text-brand-orange hover:underline">
            ← Zurück zur Startseite
          </Link>
        </p>
      </article>
    </Layout>
  );
}
