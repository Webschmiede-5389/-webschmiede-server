/**
 * DocuSeal API – Kombi-Umschlag Hauptvertrag (§ 611 BGB) + AVV (Art. 28 DSGVO).
 * Self-hosted: https://sign.digitalehandwerkskunst.de
 */
import crypto from "node:crypto";

export interface DocuSealConfig {
  baseUrl: string;
  apiToken: string;
  templateId: number;
  ownerEmail: string;
  ownerName: string;
}

export interface CustomerContact {
  name: string;
  email: string;
  company?: string;
}

export interface ComboContractOptions {
  customer: CustomerContact;
  message?: {
    subject?: string;
    body?: string;
  };
  metadata?: Record<string, string>;
}

export interface DocuSealSubmission {
  id: number;
  slug: string;
  status: string;
  submitters: Array<{ id: number; email: string; role: string; status: string }>;
}

const ROLE_CUSTOMER = "Kunde";
const ROLE_AGENCY = "Webschmiede";

function apiUrl(base: string, path: string): string {
  return `${base.replace(/\/$/, "")}${path}`;
}

function headers(token: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Auth-Token": token,
  };
}

async function parseResponse<T>(res: Response): Promise<T> {
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`DocuSeal: Ungültige JSON-Antwort (${res.status})`);
  }
  if (!res.ok) {
    const msg =
      typeof data === "object" && data && "error" in data
        ? String((data as { error: string }).error)
        : text.slice(0, 200);
    throw new Error(`DocuSeal API ${res.status}: ${msg}`);
  }
  return data as T;
}

export async function sendComboContract(
  config: DocuSealConfig,
  options: ComboContractOptions,
): Promise<DocuSealSubmission> {
  const { customer, message, metadata } = options;

  const payload = {
    template_id: config.templateId,
    send_email: true,
    order: "preserved",
    message: {
      subject: message?.subject ?? "Webschmiede – Vertrag & AVV zur Unterschrift",
      body:
        message?.body ??
        `Guten Tag ${customer.name},\n\nanbei erhalten Sie den Dienstleistungsvertrag (§ 611 BGB) sowie den Auftragsverarbeitungsvertrag (Art. 28 DSGVO) als Kombi-Umschlag.\n\nBitte prüfen und digital unterschreiben.\n\nViele Grüße\n${config.ownerName}\nWebschmiede – digitale Handwerkskunst`,
    },
    submitters: [
      {
        role: ROLE_CUSTOMER,
        email: customer.email,
        name: customer.name,
        metadata: metadata ?? {},
      },
      {
        role: ROLE_AGENCY,
        email: config.ownerEmail,
        name: config.ownerName,
      },
    ],
  };

  const res = await fetch(apiUrl(config.baseUrl, "/api/submissions"), {
    method: "POST",
    headers: headers(config.apiToken),
    body: JSON.stringify(payload),
  });

  return parseResponse<DocuSealSubmission>(res);
}

export function loadDocuSealConfigFromEnv(): DocuSealConfig {
  const baseUrl = process.env.DOCUSEAL_URL ?? "https://sign.digitalehandwerkskunst.de";
  const apiToken = process.env.DOCUSEAL_API_TOKEN ?? "";
  const templateId = Number(process.env.DOCUSEAL_TEMPLATE_COMBO_ID ?? "0");
  const ownerEmail = process.env.AGENCY_OWNER_EMAIL ?? "info@digitalehandwerkskunst.de";
  const ownerName = process.env.AGENCY_OWNER_NAME ?? "Christian Kummetat";

  if (!apiToken) throw new Error("DOCUSEAL_API_TOKEN fehlt");
  if (!templateId) throw new Error("DOCUSEAL_TEMPLATE_COMBO_ID fehlt");

  return { baseUrl, apiToken, templateId, ownerEmail, ownerName };
}

export function verifyDocuSealWebhook(
  rawBody: string,
  signatureHeader: string | undefined,
  secret: string,
): boolean {
  if (!signatureHeader || !secret) return false;
  const expected = crypto.createHmac("sha256", secret).update(rawBody).digest("hex");
  const provided = signatureHeader.replace(/^sha256=/, "");
  try {
    return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(provided));
  } catch {
    return false;
  }
}

export type ContractWebhookEvent = "submission.completed" | "contract.completed";

export interface ContractCompletedPayload {
  event: ContractWebhookEvent;
  data: {
    id: number;
    status: string;
    submitters?: Array<{ email: string; status: string }>;
    metadata?: Record<string, string>;
  };
}

export function mapToCrmStatus(payload: ContractCompletedPayload): {
  status: "signiert" | "pending" | "unknown";
  submissionId: number;
  customerEmail?: string;
} {
  const event = payload.event;
  const data = payload.data;
  const completed =
    event === "submission.completed" ||
    event === "contract.completed" ||
    data.status === "completed";

  const customer = data.submitters?.find((s) => s.status === "completed") ?? data.submitters?.[0];

  return {
    status: completed ? "signiert" : "pending",
    submissionId: data.id,
    customerEmail: customer?.email,
  };
}
