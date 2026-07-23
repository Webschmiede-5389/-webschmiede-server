import { Link } from "react-router-dom";
import { Layout, PHONE_DISPLAY, PHONE_LINK, WA, BOOKING } from "../components/Layout";
import { IntegrationsTeaser } from "../components/IntegrationsSection";

const INDUSTRIES = [
  {
    id: "gastro",
    label: "Gastronomie",
    icon: "fa-utensils",
    scene: "Bestellung kommt bei Ihnen an, nicht nur über die Liefer-App.",
  },
  {
    id: "handwerk",
    label: "Handwerk",
    icon: "fa-hammer",
    scene: "Anfrage rein, Auftrag klar, Beleg nicht erst am Sonntag suchen.",
  },
  {
    id: "dach",
    label: "Dachdecker",
    icon: "fa-house-chimney",
    scene: "Notfall um halb elf. Der Rückruf geht nicht unter.",
  },
  {
    id: "friseur",
    label: "Friseur",
    icon: "fa-scissors",
    scene: "Termin online, kurze Erinnerung, weniger leere Stühle.",
  },
  {
    id: "kfz",
    label: "Kfz-Werkstatt",
    icon: "fa-car",
    scene: "Service-Termin mit Kennzeichen. Ohne zehnmal hin und her.",
  },
];

const SYSTEMS = [
  {
    name: "Fundament",
    tagline: "Man findet Sie",
    scene: "Kunde googelt montags. Seite und Maps sagen klar, wer Sie sind und wie man anruft.",
    points: ["Website ohne Firlefanz", "Google-Eintrag, der stimmt", "Erreichbarkeit, wo man sie sucht"],
  },
  {
    name: "System",
    tagline: "Die Anfrage bleibt bei Ihnen",
    scene:
      "Bestellen, Termin, Anfrage: über Ihre Adresse. Nicht über den Zettel neben der Kasse. Nicht nur über fremde Apps.",
    points: ["Portal oder Formular unter Ihrer Domain", "Übersicht für Küche, Büro oder Werkstatt", "Weniger Abgabe an Zwischenportale"],
    highlight: true,
  },
  {
    name: "Automatik",
    tagline: "Feierabend, und es sortiert trotzdem",
    scene:
      "Erinnerung rausgeht. Kunden stehen in einer Liste. Wer mag, kriegt den Link zur Bewertung. Sonntag ohne Excel.",
    points: ["Erinnerungen (SMS geht auch)", "Kundenliste statt Zettelkasten", "Bewertung nur, wenn der Kunde mag"],
  },
];

const PROBLEMS = [
  {
    title: "Das Geld geht woanders hin.",
    text: "Lieferplattform nimmt mit. Portal nimmt mit. Am Monatsende fragen Sie sich, warum so wenig hängen bleibt.",
  },
  {
    title: "Nach Feierabend noch Büro.",
    text: "Rückrufe, Erinnerungen, „bitte bewerten“. Das liegt abends noch auf dem Tisch. Muss nicht.",
  },
  {
    title: "Google kennt Sie nicht.",
    text: "Wer in Maps nicht auftaucht, kriegt den Anruf nicht. Der Nachbar schon.",
  },
];

function PrimaryCta({
  className = "",
  children = BOOKING.label,
}: {
  className?: string;
  children?: string;
}) {
  return (
    <a href={BOOKING.url} target="_blank" rel="noreferrer" className={`btn-primary ${className}`.trim()}>
      {children}
    </a>
  );
}

function IndustryCard({ ind }: { ind: (typeof INDUSTRIES)[0] }) {
  return (
    <div className="card flex flex-col text-center">
      <div className="icon-circle mx-auto">
        <i className={`fa-solid ${ind.icon}`} aria-hidden="true" />
      </div>
      <h3 className="mt-4 font-bold text-brand-ink">{ind.label}</h3>
      <p className="mt-2 flex-1 text-sm leading-relaxed text-brand-muted">{ind.scene}</p>
    </div>
  );
}

export default function HomePage() {
  return (
    <Layout>
      {/* 1 Hook + Beweis-Chip früh */}
      <section className="border-b border-brand-border bg-white">
        <div className="mx-auto max-w-6xl px-4 py-14 md:py-24">
          <p className="section-label">Webschmiede · Mechernich</p>
          <h1 className="mt-3 max-w-4xl text-4xl font-bold leading-tight text-brand-ink md:text-5xl lg:text-6xl">
            Keine Webseite zum Anschauen. Ein System, das mitarbeitet.
          </h1>
          <p className="mt-4 max-w-2xl text-lg font-medium text-brand-orange md:text-xl">
            Bestellungen und Anfragen landen bei Ihnen. Nicht auf dem Zettel. Nicht nur bei fremden Apps.
          </p>
          <p className="mt-6 max-w-2xl leading-relaxed text-brand-muted">
            Ich war Trockenbau. Heute baue ich Portale und Automationen für Betriebe in der Eifel und
            drumherum. Live u. a. beim Snack House Mechernich. Ein Ansprechpartner. Preis nach dem
            Gespräch, nicht vorher aus der Luft.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <PrimaryCta>Gespräch buchen · 15 Min.</PrimaryCta>
            <a href={WA} target="_blank" rel="noreferrer" className="btn-outline">
              Lieber WhatsApp
            </a>
          </div>
          <p className="mt-3 text-sm text-brand-muted">
            Kein Pitch. Wir gucken, was bei Ihnen klemmt. Passt es nicht, sagen wir das auch.
          </p>
          <p className="mt-8 text-sm font-medium text-brand-ink">
            <a href="#problem" className="text-brand-orange hover:underline">
              Kommt Ihnen das bekannt vor?
            </a>{" "}
            Dann scrollen Sie weiter.
          </p>
        </div>
      </section>

      {/* 2 Wiedererkennung → Spannung */}
      <section id="problem" className="border-b border-brand-border bg-brand-orange-soft/30 py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4">
          <p className="section-label text-center">Kennen Sie das?</p>
          <h2 className="section-title mt-2 text-center">Drei Situationen, die ich ständig höre</h2>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {PROBLEMS.map((p) => (
              <div key={p.title} className="rounded-2xl border border-brand-border bg-white p-6 shadow-sm">
                <h3 className="text-lg font-bold text-brand-ink">{p.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-brand-muted">{p.text}</p>
              </div>
            ))}
          </div>
          <p className="mx-auto mt-10 max-w-xl text-center text-brand-muted">
            Die gute Nachricht: Das ist alles lösbar. Nicht mit einer schöneren Startseite. Mit dem
            Teil{" "}
            <a href="#vorher-nachher" className="font-semibold text-brand-orange hover:underline">
              danach
            </a>
            .
          </p>
        </div>
      </section>

      {/* 3 Beweis früh (Glaubwürdigkeit, bevor man kauft) */}
      <section id="vorher-nachher" className="border-b border-brand-border bg-brand-bg py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4">
          <p className="section-label">Was sich ändert</p>
          <h2 className="section-title">Schön reicht nicht. Es muss laufen.</h2>
          <p className="mt-4 max-w-2xl text-brand-muted">
            Viele haben schon eine Seite. Trotzdem: Telefon, Zettel, Chaos. Ich baue den Teil, der
            den Alltag trägt.
          </p>
          <div className="mt-10 grid gap-6 lg:grid-cols-2">
            <div className="overflow-hidden rounded-2xl border border-brand-border bg-white shadow-sm">
              <img
                src="/vorher-screenshot.jpg"
                alt="Vorher: Website ohne laufendes System"
                className="h-48 w-full object-cover object-top"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                }}
              />
              <div className="p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-brand-muted">Vorher</p>
                <p className="mt-1 font-semibold text-brand-ink">Hübsche Seite. Nichts läuft.</p>
                <ul className="mt-3 space-y-1 text-sm text-brand-muted">
                  <li>Kein Bestellen oder Buchen online</li>
                  <li>Anfragen gehen unter</li>
                  <li>Bei Google kaum sichtbar</li>
                </ul>
              </div>
            </div>
            <div className="overflow-hidden rounded-2xl border-2 border-brand-orange bg-white shadow-sm">
              <img
                src="/nachher-screenshot.jpg"
                alt="Nachher: laufendes System"
                className="h-48 w-full object-cover object-top"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                }}
              />
              <div className="p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-brand-orange">Nachher</p>
                <p className="mt-1 font-semibold text-brand-ink">Ihr System. Ihre Domain.</p>
                <ul className="mt-3 space-y-1 text-sm text-brand-muted">
                  <li>Portal und Übersicht fürs Team</li>
                  <li>Erinnerungen, wenn sie helfen</li>
                  <li>Sie arbeiten, das System hält mit</li>
                </ul>
              </div>
            </div>
          </div>
          <p className="mt-8 text-center text-sm text-brand-muted">
            Wie das bei Ihnen aussehen kann?{" "}
            <a href="#loesungen" className="font-semibold text-brand-orange hover:underline">
              Drei Stufen, kurz erklärt ↓
            </a>
          </p>
        </div>
      </section>

      {/* 4 Angebot */}
      <section id="loesungen" className="bg-white py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4">
          <p className="section-label text-center">Was ich baue</p>
          <h2 className="section-title text-center">Drei Stufen. Sie müssen nicht alles auf einmal.</h2>
          <p className="mx-auto mt-4 max-w-xl text-center text-brand-muted">
            Die meisten starten bei <strong className="font-semibold text-brand-ink">System</strong>.
            Fundament, wenn noch nichts steht. Automatik, wenn Feierabend wieder Büro ist.
          </p>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {SYSTEMS.map((sys) => (
              <div
                key={sys.name}
                className={`flex flex-col rounded-2xl border p-6 shadow-sm ${
                  sys.highlight
                    ? "border-brand-orange bg-brand-orange-soft/30 ring-1 ring-brand-orange/30"
                    : "border-brand-border bg-brand-bg"
                }`}
              >
                {sys.highlight && (
                  <span className="mb-2 text-[10px] font-bold uppercase tracking-wider text-brand-orange">
                    Hier starten die meisten
                  </span>
                )}
                <h3 className="text-xl font-bold text-brand-ink">{sys.name}</h3>
                <p className="mt-1 text-sm font-medium text-brand-orange">{sys.tagline}</p>
                <p className="mt-3 text-sm leading-relaxed text-brand-ink">{sys.scene}</p>
                <ul className="mt-4 flex flex-1 flex-col gap-2">
                  {sys.points.map((p) => (
                    <li key={p} className="flex gap-2 text-sm text-brand-muted">
                      <i className="fa-solid fa-check mt-1 shrink-0 text-brand-orange" aria-hidden />
                      {p}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div
            id="buchhaltung"
            className="mt-12 rounded-2xl border border-brand-border bg-brand-bg p-6 md:p-8"
          >
            <p className="text-xs font-bold uppercase tracking-widest text-brand-orange">Falls das auch nervt</p>
            <h3 className="mt-2 text-xl font-bold text-brand-ink">
              „Wo ist der Beleg zu Auftrag 847?“
            </h3>
            <p className="mt-2 max-w-2xl leading-relaxed text-brand-muted">
              Die Kanzlei bucht weiter in DATEV. Sie schieben nur noch ordentliche Unterlagen rüber.
              Keine zweite Buchhaltung. Dazu buchbar, kein Muss.
            </p>
          </div>

          <div className="mt-10 rounded-2xl border border-brand-border bg-brand-bg p-6 md:flex md:items-center md:justify-between md:gap-8 md:p-8">
            <div>
              <h3 className="text-xl font-bold text-brand-ink">So läuft ein Auftrag bei mir</h3>
              <ol className="mt-4 grid gap-3 sm:grid-cols-3">
                {[
                  ["1", "Kurz reden", "Was klemmt? Was soll besser laufen?"],
                  ["2", "Ich baue", "Einrichten, testen, fertig machen."],
                  ["3", "Live", "Online. Kurze Einweisung. Danach bleibe ich erreichbar."],
                ].map(([n, t, d]) => (
                  <li key={n}>
                    <p className="text-sm font-bold text-brand-orange">{n} · {t}</p>
                    <p className="mt-1 text-sm text-brand-muted">{d}</p>
                  </li>
                ))}
              </ol>
            </div>
            <div className="mt-6 flex shrink-0 flex-col items-start gap-2 md:mt-0">
              <PrimaryCta>Gespräch buchen · 15 Min.</PrimaryCta>
              <p className="text-xs text-brand-muted">Do/Fr nachmittags · oder WhatsApp</p>
            </div>
          </div>
        </div>
      </section>

      {/* 5 Branchen = Identifikation */}
      <section id="branchen" className="border-t border-brand-border bg-white py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4">
          <p className="section-label text-center">Ihr Alltag</p>
          <h2 className="section-title mt-2 text-center">Gleicher Aufbau. Anderer Laden.</h2>
          <p className="mx-auto mt-4 max-w-xl text-center text-brand-muted">
            Ob Imbiss oder Werkstatt: Die Stufen bleiben. Die Sprache wird Ihre.
          </p>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {INDUSTRIES.map((ind) => (
              <IndustryCard key={ind.id} ind={ind} />
            ))}
          </div>
        </div>
      </section>

      {/* 6 Risiko runter */}
      <section id="vertrauen" className="border-y border-brand-border bg-brand-bg py-14 md:py-16">
        <div className="mx-auto max-w-3xl px-4 text-center">
          <p className="section-label">Bevor Sie zögern</p>
          <h2 className="section-title mt-2">Server in Deutschland. Ich bleibe am Telefon.</h2>
          <p className="mt-4 leading-relaxed text-brand-muted">
            Technik im Maschinenraum. Für Sie zählt: Es läuft. Kundendaten liegen nicht unnötig in
            irgendwelchen US-Clouds. Brauchen wir einen AVV, gibt es den. Backups laufen. Nach dem
            Start tauche ich nicht ab.
          </p>
          <p className="mt-4 text-xs text-brand-muted">
            ISO-27001 hat das Rechenzentrum vom Hoster, nicht ich als Stempel auf der Visitenkarte.
          </p>
        </div>
      </section>

      <IntegrationsTeaser />

      {/* 7 Mensch */}
      <section id="warum" className="bg-white py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-4">
          <div className="grid items-center gap-10 lg:grid-cols-2">
            <div className="flex justify-center">
              <div className="h-64 w-64 overflow-hidden rounded-2xl border-2 border-brand-orange-border shadow-md">
                <img
                  src="/christian-kummetat.jpg"
                  alt="Christian Kummetat"
                  className="h-full w-full object-cover"
                  onError={(e) => {
                    const t = e.currentTarget;
                    t.style.display = "none";
                    if (t.parentElement) {
                      t.parentElement.className +=
                        " flex items-center justify-center bg-brand-orange-soft";
                      t.parentElement.innerHTML =
                        '<div class="text-center"><p class="text-5xl font-bold text-brand-orange">CK</p></div>';
                    }
                  }}
                />
              </div>
            </div>
            <div>
              <p className="section-label">Wer das baut</p>
              <h2 className="section-title">Handwerk kenne ich. Systeme baue ich.</h2>
              <p className="mt-2 font-medium text-brand-orange">Christian Kummetat · Mechernich</p>
              <blockquote className="mt-4 border-l-4 border-brand-orange pl-4 text-brand-muted">
                Früher Wände. Heute Systeme. Gleiche Regel: ordentlich machen, damit es hält.
              </blockquote>
              <ul className="mt-6 space-y-2 text-sm text-brand-muted">
                <li>
                  <strong className="text-brand-ink">Preis:</strong> erst gucken, dann sagen.
                </li>
                <li>
                  <strong className="text-brand-ink">Ansprechpartner:</strong> ich. Kein Callcenter.
                </li>
                <li>
                  <strong className="text-brand-ink">Danach:</strong> Support bleibt.
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* 8 Abschluss = eine klare Handlung */}
      <section className="border-t border-brand-border bg-brand-orange-soft/50 py-16 md:py-20">
        <div className="mx-auto max-w-2xl px-4 text-center">
          <h2 className="section-title">Nächster Schritt: 15 Minuten.</h2>
          <p className="mt-4 text-brand-muted">
            Sie erzählen, was klemmt. Ich sage, ob und wie ich helfen kann. Kein Verkaufsmarathon.
            Wenn es nicht passt, sagen wir das.
          </p>
          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <PrimaryCta className="w-full sm:w-auto">Gespräch buchen · 15 Min.</PrimaryCta>
            <a href={WA} target="_blank" rel="noreferrer" className="btn-outline w-full sm:w-auto">
              WhatsApp schreiben
            </a>
          </div>
          <p className="mt-4 text-sm text-brand-muted">
            Oder anrufen:{" "}
            <a href={PHONE_LINK} className="font-bold text-brand-orange hover:underline">
              {PHONE_DISPLAY}
            </a>
          </p>
          <p className="mt-8 text-sm text-brand-muted">
            Schon Kunde und es hakt?{" "}
            <Link to="/support" className="font-semibold text-brand-orange hover:underline">
              Support
            </Link>
          </p>
        </div>
      </section>
    </Layout>
  );
}
