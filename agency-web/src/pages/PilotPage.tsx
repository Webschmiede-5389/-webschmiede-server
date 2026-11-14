import { useEffect, useRef, useState } from 'react';
import { BOOKING } from '../lib/config';

// Contact destinations observed on the live website on 2026-11-14.
const live = 'https://digitalehandwerkskunst.de';
const phone = 'tel:+491791598184';
const whatsapp = 'https://wa.me/491791598184';
const email = 'mailto:info@digitalehandwerkskunst.de';
const scenarios = [
  { name: 'Handwerk', short: 'Anfrage', title: 'Der Rückruf geht nicht unter.', question: '„Könnt ihr unser Bad renovieren?“', source: 'Anfrage über deine Website', task: 'Rückruf für morgen vormerken', result: 'Du weißt, wer auf eine Antwort wartet.', description: 'Der Kunde beschreibt sein Vorhaben. Die Anfrage landet mit den wichtigen Angaben an einem Ort. Dein Team sieht, was als Nächstes dran ist.', type: 'Anfrage aufnehmen', second: 'Nächsten Schritt festhalten', third: 'Überblick behalten' },
  { name: 'Gastronomie', short: 'Bestellung', title: 'Die Bestellung findet ihren Weg.', question: '„Zwei Burger, Abholung um 19 Uhr.“', source: 'Bestellung über dein Portal', task: 'Bestellung für die Küche anzeigen', result: 'Küche und Kunde kennen den nächsten Schritt.', description: 'Gäste wählen direkt auf deiner Seite. Die Küche sieht die Bestellung. Welche Zahlarten und Abläufe passen, klären wir vorher gemeinsam.', type: 'Bestellung aufnehmen', second: 'An die Küche weitergeben', third: 'Abholung vorbereiten' },
  { name: 'Dienstleistung', short: 'Termin', title: 'Der Termin steht. Der Kopf ist frei.', question: '„Habt ihr am Freitag noch einen Termin?“', source: 'Buchung über deine Website', task: 'Bestätigung für den Kunden vorbereiten', result: 'Der Termin steht im richtigen Kalender.', description: 'Kunden wählen einen verfügbaren Termin. Die Buchung landet im Kalender. Eine passende Erinnerung kann den Ablauf ergänzen.', type: 'Termin auswählen', second: 'Buchung bestätigen', third: 'Termin im Blick behalten' },
  { name: 'Büro & B2B', short: 'Kontakt', title: 'Aus einer Nachricht wird ein klarer Vorgang.', question: '„Wir suchen ein Büro für vier Personen.“', source: 'Kontakt über deine Website', task: 'Anfrage der richtigen Person zuordnen', result: 'Dein Team sieht, wer sich darum kümmert.', description: 'Die Anfrage kommt mit den nötigen Informationen an. Eine zuständige Person übernimmt. Der Bearbeitungsstand bleibt für dein Team nachvollziehbar.', type: 'Bedarf erfassen', second: 'Zuständigkeit klären', third: 'Bearbeitung verfolgen' },
];

function Arrow({ diagonal = false }: { diagonal?: boolean }) { return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d={diagonal ? 'M5 19 19 5M5 5h14v14' : 'M4 12h15m-6-6 6 6-6 6'}/></svg>; }
function Icon({ kind }: { kind: 'message'|'grid'|'check'|'clock'|'bolt' }) {
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{kind === 'message' ? <path d="M4 4h16v12H9l-5 4V4Z M8 8h8M8 12h5"/> : kind === 'grid' ? <><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></> : kind === 'check' ? <path d="m5 12 4 4L19 6"/> : kind === 'clock' ? <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></> : <path d="m13 3-8 11h6l-1 7 9-12h-6l1-6Z"/>}</svg>;
}
function Book({ children = 'Lass uns sprechen', secondary = false }: { children?: React.ReactNode; secondary?: boolean }) {
  return <a className={`ws-button ${secondary ? 'ws-button-light' : ''}`} href={BOOKING.url} target="_blank" rel="noreferrer">{children}<Arrow diagonal /></a>;
}
const faqs = [
  ['Was kostet die Zusammenarbeit?', 'Das hängt davon ab, was dein Betrieb braucht. Im ersten Gespräch grenzen wir den Umfang ein. Danach bekommst du ein Angebot, das Einrichtung, laufende Kosten und Betreuung nachvollziehbar trennt. Du entscheidest vor dem Start.'],
  ['Muss ich meine bestehende Website ersetzen?', 'Das klären wir zuerst. Wenn deine Website ihren Zweck erfüllt, kann eine Ergänzung sinnvoller sein. Zum Beispiel ein Buchungsweg oder ein Formular, das die richtigen Informationen abfragt.'],
  ['Können meine bisherigen Programme bleiben?', 'Wir schauen gemeinsam, was du schon nutzt und welche Anbindungen verfügbar sind. Ob Kalender, Kundenverwaltung oder Buchhaltung: Eine Verbindung wird erst zugesagt, wenn die technische Möglichkeit geprüft ist.'],
  ['Was passiert nach dem Start?', 'Du bekommst eine Einweisung und weißt, an wen du dich wenden kannst. Welchen Support, welche Wartung und welche laufenden Leistungen du erhältst, halten wir im Angebot fest.'],
  ['Wo liegen die Daten?', 'Für eigene Systeme ist Hosting in Deutschland vorgesehen. Welche weiteren Anbieter beteiligt sind und welche Daten sie verarbeiten, klären wir für dein konkretes Projekt. Das hängt auch von den Programmen ab, die du anbinden möchtest.'],
];

export default function PilotPage() {
  const [menu, setMenu] = useState(false);
  const [industry, setIndustry] = useState(0);
  const [step, setStep] = useState(0);
  const menuButton = useRef<HTMLButtonElement>(null);
  const nav = useRef<HTMLElement>(null);
  const scenario = scenarios[industry];
  useEffect(() => {
    if (!menu) return;
    nav.current?.querySelector('a')?.focus();
    function escape(event: KeyboardEvent) { if (event.key === 'Escape') { setMenu(false); menuButton.current?.focus(); } }
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [menu]);
  return <div className="ws-page">
    <a className="ws-skip" href="#inhalt">Zum Inhalt</a>
    <header className="ws-header">
      <a className="ws-brand" href="#" aria-label="Webschmiede Startseite"><img src="/ci/webschmiede-logo.png" width="1114" height="273" alt="Webschmiede · Digitale Handwerkskunst"/></a>
      <nav ref={nav} id="pilot-navigation" className={`ws-nav ${menu ? 'is-open' : ''}`} aria-label="Hauptnavigation">
        <a href="#loesungen" onClick={() => setMenu(false)}>Was ich baue</a><a href="#alltag" onClick={() => setMenu(false)}>Dein Alltag</a><a href="#christian" onClick={() => setMenu(false)}>Über mich</a>
        <a className="ws-mobile-contact" href={`${live}/login`}>Kundenlogin <Arrow diagonal/></a><a className="ws-mobile-contact" href="#kontakt" onClick={() => setMenu(false)}>Kontakt aufnehmen <Arrow/></a>
      </nav>
      <div className="ws-header-actions"><a className="ws-login" href={`${live}/login`}>Kundenlogin <Arrow diagonal/></a><a className="ws-header-cta" href="#kontakt">Projekt besprechen <Arrow/></a><button className="ws-menu-toggle" ref={menuButton} aria-expanded={menu} aria-controls="pilot-navigation" aria-label={menu ? 'Menü schließen' : 'Menü öffnen'} onClick={() => setMenu(!menu)}><span/ ><span/></button></div>
    </header>

    <main id="inhalt">
      <section className="ws-hero ws-wrap">
        <div className="ws-hero-copy">
          <p className="ws-eyebrow"><span className="ws-dot"/> Digitale Handwerkskunst aus Mechernich</p>
          <h1>Dein Betrieb <br/>läuft.<br/><span>Dein Büro auch.</span></h1>
          <p className="ws-lead">Du machst gute Arbeit. Ich baue die Website und die Abläufe dahinter, damit Anfragen ankommen und nach Feierabend weniger liegen bleibt.</p>
          <div className="ws-actions"><Book/><a className="ws-text-link" href="#alltag">So kann das aussehen <Arrow/></a></div>
          <div className="ws-person-note"><img src="/christian-kummetat.jpg" width="44" height="44" alt=""/><span>Mit Christian. Direkt und persönlich.<small>15 Minuten, um deinen Betrieb kennenzulernen.</small></span></div>
        </div>
        <div className="ws-workbench" aria-label="Illustration: Aus einer Kundenanfrage wird ein geordneter Ablauf">
          <div className="ws-workbench-top"><span>DEIN BETRIEB. GUT VERBUNDEN.</span><span className="ws-cross">+</span></div>
          <div className="ws-workbench-grid" aria-hidden="true"/>
          <div className="ws-note ws-note-one"><Icon kind="message"/><span>„Kannst du<br/>mich zurückrufen?“</span><span className="ws-note-time">09:41</span></div>
          <div className="ws-note ws-note-two"><Icon kind="clock"/><span>Termin anfragen</span><span className="ws-mini-dot"/></div>
          <svg className="ws-connectors" viewBox="0 0 520 530" fill="none" aria-hidden="true"><path d="M114 153v78q0 20 20 20h122m120-75v55q0 20-20 20H256v70" stroke="#b4ada1" strokeWidth="1.5" strokeDasharray="4 5"/><path className="ws-draw-line" d="M256 321v64q0 22 22 22h64" stroke="#ff6600" strokeWidth="3"/></svg>
          <div className="ws-engine"><span className="ws-engine-icon"><Icon kind="grid"/></span><div><small>ALLES AN SEINEM PLATZ</small><strong>Dein digitaler Ablauf</strong><span>Auf deinen Betrieb abgestimmt.</span></div><span className="ws-engine-plus">+</span></div>
          <div className="ws-done"><span className="ws-check-circle"><Icon kind="check"/></span><div><small>NÄCHSTER SCHRITT</small><strong>Rückruf ist vorgemerkt.</strong><span>Der Kopf kann wieder bei der Arbeit sein.</span></div></div>
          <div className="ws-workbench-bottom"><span>01 / VOM DURCHEINANDER ZUM ABLAUF</span><span>Beispielhafte Darstellung</span></div>
        </div>
      </section>

      <div className="ws-industry-strip"><div className="ws-wrap"><span>Für Betriebe, die anpacken.</span><span>Handwerk</span><i>+</i><span>Gastronomie</span><i>+</i><span>Dienstleistung</span><i>+</i><span>Büro &amp; B2B</span></div></div>

      <section className="ws-problem ws-wrap ws-section">
        <div><p className="ws-eyebrow">01 / Die Baustelle im Alltag</p><h2>Gute Arbeit. <br/>Zu viele<br/><span className="ws-muted-heading">offene Enden.</span></h2></div>
        <div className="ws-problem-list">
          <article><span>01</span><div><h3>Die Anfrage ist irgendwo.</h3><p>Eine Nachricht auf WhatsApp. Ein Anruf zwischendurch. Abends suchst du, wem du noch antworten wolltest.</p></div><Icon kind="message"/></article>
          <article><span>02</span><div><h3>Nach Feierabend wartet das Büro.</h3><p>Termine bestätigen, Informationen übertragen, hinterhertelefonieren. Die gleiche Arbeit, jeden Tag.</p></div><Icon kind="clock"/></article>
          <article><span>03</span><div><h3>Die Website hört beim Anschauen auf.</h3><p>Dein Kunde findet dich. Aber der nächste Schritt ist umständlich. Dabei könnte er direkt anfragen, buchen oder bestellen.</p></div><Icon kind="bolt"/></article>
        </div>
      </section>

      <section className="ws-demo" id="alltag">
        <div className="ws-wrap ws-section">
          <div className="ws-section-top"><div><p className="ws-eyebrow">02 / So greifen die Dinge ineinander</p><h2>Ein Klick beim Kunden.<br/><span>Ein klarer Ablauf bei dir.</span></h2></div><p>Wähle deinen Alltag und geh einen möglichen Ablauf durch. Was dein Betrieb braucht, legen wir gemeinsam fest.</p></div>
          <div className="ws-tabs" role="group" aria-label="Branche wählen">{scenarios.map((item, i) => <button key={item.name} aria-pressed={industry === i} onClick={() => { setIndustry(i); setStep(0); }}>{item.name}<Arrow diagonal/></button>)}</div>
          <div className="ws-demo-layout">
            <div className="ws-demo-story"><span className="ws-demo-label">BEISPIEL · {scenario.name.toUpperCase()}</span><h3>{scenario.title}</h3><p>{scenario.description}</p><ol className="ws-steps">{[scenario.type, scenario.second, scenario.third].map((label, i) => <li key={label}><button aria-pressed={step === i} onClick={() => setStep(i)}><span>0{i + 1}</span>{label}<Arrow/></button></li>)}</ol></div>
            <div className="ws-demo-screen" aria-live="polite" aria-atomic="true">
              <div className="ws-screen-top"><span><span/><span/><span/></span><small>So könnte dein Ablauf aussehen</small><Icon kind="grid"/></div>
              <div className="ws-screen-body" key={`${industry}-${step}`}><p className="ws-screen-counter">SCHRITT 0{step + 1} <span>/ 03</span></p><div className="ws-screen-icon"><Icon kind={step === 0 ? 'message' : step === 1 ? 'clock' : 'check'}/></div><h4>{step === 0 ? scenario.question : step === 1 ? scenario.task : scenario.result}</h4><p>{step === 0 ? scenario.source : step === 1 ? 'Informationen bleiben beim Vorgang.' : 'Ein Ablauf. Für deinen Betrieb gebaut.'}</p><div className="ws-sample-row"><span>{scenario.short}</span><span className="ws-status"><span/>{step === 0 ? 'Eingegangen' : step === 1 ? 'Zugeordnet' : 'Im Blick'}</span></div><button className="ws-demo-next" onClick={() => setStep((step + 1) % 3)}>{step === 2 ? 'Noch einmal ansehen' : 'Nächster Schritt'}<Arrow/></button></div>
              <div className="ws-screen-footer">Beispielhafter Ablauf. Wird an deinen Betrieb angepasst.</div>
            </div>
          </div>
        </div>
      </section>

      <section className="ws-services ws-wrap ws-section" id="loesungen">
        <div className="ws-section-top"><div><p className="ws-eyebrow">03 / Was ich für dich baue</p><h2>Genau das,<br/>was dich weiterbringt.</h2></div><p>Wir starten da, wo es klemmt. Manchmal ist das eine neue Website. Manchmal ein einziger Ablauf, der dir jeden Tag Arbeit abnimmt.</p></div>
        <div className="ws-service-row"><span className="ws-service-number">01</span><h3>Eine Website,<br/>die den Weg zeigt.</h3><div><p>Dein Angebot verständlich erklären. Vertrauen aufbauen. Und Kunden zum richtigen nächsten Schritt führen.</p><span>Website · Kontakt · Buchungseinstieg</span></div><a href="#kontakt" aria-label="Website-Projekt besprechen"><Arrow diagonal/></a></div>
        <div className="ws-service-row"><span className="ws-service-number">02</span><h3>Ein Ablauf,<br/>der zu dir passt.</h3><div><p>Vom Formular bis zur Bearbeitung. Ein Bestellportal, eine Terminbuchung oder eine Übersicht fürs Team.</p><span>Portale · Kundenanfragen · Terminabläufe</span></div><a href="#kontakt" aria-label="Digitalen Ablauf besprechen"><Arrow diagonal/></a></div>
        <div className="ws-service-row"><span className="ws-service-number">03</span><h3>Weniger Arbeit,<br/>die sich wiederholt.</h3><div><p>Informationen weitergeben, Erinnerungen vorbereiten und vorhandene Programme sinnvoll verbinden.</p><span>Automationen · Anbindungen · Einweisung</span></div><a href="#kontakt" aria-label="Automatisierung besprechen"><Arrow diagonal/></a></div>
        <p className="ws-service-note">Was es kostet? Nach einem Blick auf deinen Betrieb gibt es ein konkretes Angebot. <a href="#fragen">Mehr zur Zusammenarbeit <Arrow/></a></p>
      </section>

      <section className="ws-about" id="christian"><div className="ws-wrap ws-about-grid">
        <div className="ws-portrait"><span className="ws-portrait-cross" aria-hidden="true">+</span><img src="/christian-kummetat.jpg" alt="Christian Kummetat, dein Ansprechpartner bei Webschmiede" width="461" height="615" loading="lazy"/><div className="ws-portrait-caption"><strong>Christian Kummetat</strong><span>Webschmiede · Mechernich, Eifel</span></div></div>
        <div className="ws-about-copy"><p className="ws-eyebrow">04 / Der Mensch hinter der Webschmiede</p><h2>Früher Wände.<br/>Heute digitale<br/><span>Abläufe.</span></h2><p>Ich komme aus dem Trockenbau. Ich weiß, wie ein Arbeitstag aussieht, an dem ständig etwas dazwischenkommt.</p><p>Deshalb höre ich zuerst zu. Dann baue ich eine Lösung, die in deinem Betrieb etwas übernimmt. Und ich erkläre sie dir so, dass du damit arbeiten kannst.</p><div className="ws-signoff"><span className="ws-sign-line"/><strong>Ordentlich machen.<br/>Damit es im Alltag hilft.</strong></div><a className="ws-text-link" href={phone}>Sprich direkt mit mir <Arrow diagonal/></a></div>
      </div></section>

      <section className="ws-process ws-wrap ws-section" id="ablauf"><div className="ws-section-top"><div><p className="ws-eyebrow">05 / Von der Idee in deinen Betrieb</p><h2>Du musst die Technik<br/>nicht vorher verstehen.</h2></div><p>Du kennst deinen Betrieb. Ich kümmere mich darum, dass daraus ein verständlicher digitaler Ablauf wird.</p></div><div className="ws-process-grid">
        <article><span>01 <i/></span><h3>Wir schauen hin.</h3><p>Was kostet dich Zeit? Was funktioniert schon? Wir finden einen sinnvollen Anfang und klären den Umfang.</p><small>Gespräch &amp; Angebot</small></article>
        <article><span>02 <i/></span><h3>Du siehst, was entsteht.</h3><p>Du bekommst einen konkreten Entwurf. Wir prüfen den Weg auf dem Computer und dem Handy, bevor er online geht.</p><small>Entwurf &amp; gemeinsamer Test</small></article>
        <article><span>03 <i/></span><h3>Es geht in den Alltag.</h3><p>Nach deiner Freigabe starten wir. Du bekommst eine Einweisung. Die weitere Betreuung vereinbaren wir passend zum Projekt.</p><small>Start &amp; Betreuung</small></article>
      </div></section>

      <section className="ws-faq ws-wrap" id="fragen"><div><p className="ws-eyebrow">Noch kurz geklärt</p><h2>Gute Fragen.<br/>Klare Antworten.</h2><a className="ws-text-link" href={whatsapp} target="_blank" rel="noreferrer">Deine Frage ist nicht dabei? <Arrow diagonal/></a></div><div>{faqs.map(([q, a]) => <details key={q}><summary>{q}<span aria-hidden="true">+</span></summary><p>{a}</p></details>)}</div></section>

      <section className="ws-contact" id="kontakt"><div className="ws-wrap"><div className="ws-contact-top"><p className="ws-eyebrow">Dein nächster Schritt</p><span>MECHERNICH / EIFEL / AUCH DIGITAL</span></div><h2>Was bleibt bei dir<br/><span>immer liegen?</span></h2><div className="ws-contact-bottom"><p>Erzähl es mir. In 15 Minuten schauen wir,<br/>ob und wie ich dir helfen kann.</p><div className="ws-actions"><Book>Gespräch buchen · 15 Min.</Book><a className="ws-whatsapp" href={whatsapp} target="_blank" rel="noreferrer">Lieber per WhatsApp <Arrow diagonal/></a></div></div></div></section>
    </main>
    <footer className="ws-footer ws-wrap"><div className="ws-footer-top"><a className="ws-brand" href="#" aria-label="Zurück zum Anfang"><img src="/ci/webschmiede-logo.png" width="1114" height="273" alt="Webschmiede · Digitale Handwerkskunst" loading="lazy"/></a><a href={email}>info@digitalehandwerkskunst.de <Arrow diagonal/></a><a href={phone}>0179 1598184 <Arrow diagonal/></a></div><div className="ws-footer-bottom"><p>© {new Date().getFullYear()} Christian Kummetat · Mechernich</p><nav aria-label="Service und Rechtliches">{[['Support','support'],['Anbindungen','anbindungen'],['Impressum','impressum'],['Datenschutz','datenschutz'],['Markenhinweise','markenhinweise']].map(([name,path]) => <a key={path} href={`${live}/${path}`}>{name}</a>)}</nav></div><p className="ws-preview-note">Gestaltungsentwurf zur Abnahme. Kontakt- und Servicelinks führen zu den bestehenden Angeboten.</p></footer>
  </div>;
}
