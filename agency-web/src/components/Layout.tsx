import { Link } from "react-router-dom";
import { ConsentBanner, ConsentResetLink } from "./ConsentBanner";
import { BOOKING } from "../lib/config";

const PHONE_DISPLAY = "0177 8011350";
const PHONE_LINK = "tel:+491778011350";
const EMAIL = "info@digitalehandwerkskunst.de";
const MAILTO = `mailto:${EMAIL}?subject=${encodeURIComponent("Anfrage WebSchmiede")}`;
const WA = "https://wa.me/491778011350";

function BrandMark({
  className = "h-10 w-auto max-w-[220px]",
}: {
  className?: string;
}) {
  return (
    <img
      src="/webschmiede-logo.png"
      alt="WebSchmiede · Digitale Handwerkskunst"
      className={`${className} shrink-0 object-contain object-left`}
    />
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-brand-bg">
      <header className="sticky top-0 z-50 border-b border-brand-border bg-white/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link
            to="/"
            className="flex min-w-0 items-center gap-3"
            aria-label="WebSchmiede, Digitale Handwerkskunst"
          >
            <BrandMark />
          </Link>

          <nav className="hidden items-center gap-5 text-sm font-medium text-brand-muted lg:flex">
            <a href="/#loesungen" className="hover:text-brand-orange">
              Leistungen
            </a>
            <a href="/#branchen" className="hover:text-brand-orange">
              Beispiele
            </a>
            <a href="/#vertrauen" className="hover:text-brand-orange">
              Vertrauen
            </a>
            <a href="/#warum" className="hover:text-brand-orange">
              Über mich
            </a>
            <Link to="/support" className="hover:text-brand-orange">
              Support
            </Link>
          </nav>

          <div className="flex shrink-0 items-center gap-2">
            <a href={PHONE_LINK} className="btn-outline hidden text-sm sm:inline-flex">
              {PHONE_DISPLAY.replace(/\s/g, "\u00a0")}
            </a>
            <a href={BOOKING.url} target="_blank" rel="noreferrer" className="btn-primary text-sm">
              {BOOKING.label}
            </a>
          </div>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-brand-border bg-white py-10">
        <div className="mx-auto max-w-6xl px-4">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <BrandMark className="h-12 w-auto max-w-[240px]" />
            </div>
            <p className="text-sm text-brand-muted">Christian Kummetat · Mechernich</p>

            <div className="flex flex-wrap gap-4 text-sm text-brand-muted">
              <a href={BOOKING.url} target="_blank" rel="noreferrer" className="hover:text-brand-orange">
                {BOOKING.label}
              </a>
              <Link to="/anbindungen" className="hover:text-brand-orange">
                Anbindungen
              </Link>
              <Link to="/impressum" className="hover:text-brand-orange">
                Impressum
              </Link>
              <Link to="/datenschutz" className="hover:text-brand-orange">
                Datenschutz
              </Link>
              <Link to="/markenhinweise" className="hover:text-brand-orange">
                Markenhinweise
              </Link>
              <Link to="/support" className="hover:text-brand-orange">
                Support
              </Link>
              <a href={MAILTO} className="hover:text-brand-orange">
                {EMAIL}
              </a>
              <a href={WA} target="_blank" rel="noreferrer" className="hover:text-brand-orange">
                WhatsApp
              </a>
            </div>
          </div>

          <p className="mt-6 text-xs leading-relaxed text-brand-muted">
            Produktnamen und Logos Dritter dienen der identifizierenden Benennung kompatibler
            Systeme, keine Partnerschaft.{" "}
            <Link to="/markenhinweise" className="text-brand-orange hover:underline">
              Markenhinweise
            </Link>
          </p>

          <p className="mt-2 text-xs text-brand-muted">
            © {new Date().getFullYear()} WebSchmiede · Digitale Handwerkskunst · {PHONE_DISPLAY} ·{" "}
            {EMAIL}
            {" · "}
            <ConsentResetLink className="text-brand-orange hover:underline" />
          </p>
        </div>
      </footer>

      <ConsentBanner />
    </div>
  );
}

export { PHONE_DISPLAY, PHONE_LINK, EMAIL, WA };
export { BOOKING } from "../lib/config";
