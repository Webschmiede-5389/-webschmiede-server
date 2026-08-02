# Customer Branding & Branding-Modi

## Modi

### 1. AGENCY_INTERNAL

Interne Systeme der Digitalen Handwerkskunst.

- WebSchmiede-Logo + Unterzeile Digitale Handwerkskunst  
- Weiß / hellgrau + Orange `#FF6600`  
- Keine Kundenfarben in der Shell

Beispiele: Cockpit, CRM (Agentur-Ansicht), Lead Creator, Nils, Setup

### 2. AGENCY_CUSTOMER_MANAGEMENT

Interne Verwaltung von Kundenprojekten.

- Agency-Logo bleibt führend  
- Kundenlogo optional als Kontext-Chip (nicht Sidebar-Ersatz)

Beispiele: Cockpit Kunden-Detail, Preview Studio Kundenliste

### 3. CUSTOMER_PORTAL

Kundenportal (Admin/Konto für den Betrieb).

- Tenant Branding über kontrollierte Tokens  
- WebSchmiede dezent als technischer Betreiber möglich  
- Keine freien Kunden-CSS-Eingaben

### 4. PUBLIC_CUSTOMER_SITE

Öffentliche Kundenwebsite / Bestellseite.

- Eigenes Kundenbranding  
- Agency-Orange **nicht** erzwingen  

Beispiel: snackhouse-yassine.de

### 5. EXTERNAL_SERVICE

Retell, Placetel, Meta, Google, n8n, Cal.com, DocuSeal, Umami.

- UI nicht manipulieren  
- Im Cockpit nur ToolCard + optional gebrandete Zwischenseite  
- Nie behaupten, Vendor sei „vollständig gebrandet“

## Tenant Branding Config (Kundenportale)

Erlaubt (strukturiert):

```json
{
  "tenant_name": "Snack House Yassine",
  "tenant_logo": "/brand/snackhouse-yassine-logo.png",
  "primary_color": "#C9A84C",
  "accent_color": "#e8c76a",
  "support_contact": "…",
  "favicon": "/favicon.png",
  "portal_title": "Bestellen"
}
```

**Verboten:** freies CSS, beliebige Font-URLs, Remote-Logo ohne Allowlist, Agency-SMTP als Shop-From.

Bestehende Quelle: `kunden/*.json` → `brand` + `client_brand.py` / Tischaufsteller-Rules.
