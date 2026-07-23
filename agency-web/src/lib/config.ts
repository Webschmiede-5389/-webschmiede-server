/** Zentrale Konfiguration – digitalehandwerkskunst.de */

export const COMPANY = {
  legalName: "Christian Kummetat",
  brandName: "Webschmiede – digitale Handwerkskunst",
  street: "Meinertzhagener Str. 16",
  zipCity: "53894 Mechernich",
  country: "Deutschland",
  phone: "0177 8011350",
  phoneLink: "tel:+491778011350",
  email: "info@digitalehandwerkskunst.de",
  vatId: "DE370109681",
  siteUrl: import.meta.env.VITE_PUBLIC_SITE_URL || "https://digitalehandwerkskunst.de",
} as const;

export const SLA = {
  criticalResponseHours: 4,
  businessHours: "Mo–Fr, 9–17 Uhr",
  note: "Reaktionszeit bei kritischem Systemausfall: max. 4 Std. (Mo–Fr, 9–17 Uhr)",
} as const;

export const N8N = {
  supportWebhook:
    import.meta.env.VITE_N8N_SUPPORT_WEBHOOK_URL ||
    "https://digitalehandwerkskunst.de/n8n/webhook/support-ticket",
  contractWebhook:
    import.meta.env.VITE_N8N_CONTRACT_WEBHOOK_URL ||
    "https://digitalehandwerkskunst.de/n8n/webhook/contract-request",
} as const;

/** Cal.com – Erstgespräch / Terminbuchung (self-hosted) */
export const BOOKING = {
  url:
    import.meta.env.VITE_CALCOM_URL ||
    "https://cal.digitalehandwerkskunst.de/christian/erstgespraech",
  label: "Gespräch buchen",
} as const;

export const VAT_RATE = 0.19;
