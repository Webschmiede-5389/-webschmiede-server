#!/usr/bin/env node
import http from "node:http";
import {
  mapToCrmStatus,
  type ContractCompletedPayload,
  verifyDocuSealWebhook,
} from "../lib/contracts.js";

const PORT = Number(process.env.WEBHOOK_PORT ?? 8787);
const DOCUSEAL_WEBHOOK_SECRET = process.env.DOCUSEAL_WEBHOOK_SECRET ?? "";
const CRM_WEBHOOK_URL =
  process.env.CRM_STATUS_WEBHOOK_URL ??
  "https://digitalehandwerkskunst.de/n8n/webhook/contract-completed";
const CRM_API_KEY = process.env.CRM_API_KEY ?? "";

async function updateCrmStatus(payload: ContractCompletedPayload): Promise<void> {
  const mapped = mapToCrmStatus(payload);

  const res = await fetch(CRM_WEBHOOK_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(CRM_API_KEY ? { Authorization: `Bearer ${CRM_API_KEY}` } : {}),
    },
    body: JSON.stringify({
      event: payload.event ?? "contract.completed",
      data: payload.data,
      action: "set_status",
      status: mapped.status === "signiert" ? "Signiert" : mapped.status,
      submission_id: mapped.submissionId,
      customer_email: mapped.customerEmail,
      source: "docuseal-webhook",
      received_at: new Date().toISOString(),
    }),
  });
  if (!res.ok) {
    throw new Error(`CRM webhook ${res.status}`);
  }
}

const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: true }));
    return;
  }

  if (req.method !== "POST" || req.url !== "/api/webhooks/docuseal") {
    res.writeHead(404);
    res.end("Not found");
    return;
  }

  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(chunk as Buffer);
  const rawBody = Buffer.concat(chunks).toString("utf8");

  const signature = req.headers["x-docuseal-signature"] as string | undefined;
  if (DOCUSEAL_WEBHOOK_SECRET) {
    const valid = verifyDocuSealWebhook(rawBody, signature, DOCUSEAL_WEBHOOK_SECRET);
    if (!valid) {
      res.writeHead(401);
      res.end(JSON.stringify({ ok: false, error: "invalid signature" }));
      return;
    }
  }

  try {
    const payload = JSON.parse(rawBody) as ContractCompletedPayload;
    const event = payload.event ?? (payload as unknown as { type?: string }).type;

    if (
      event === "submission.completed" ||
      event === "contract.completed" ||
      payload.data?.status === "completed"
    ) {
      await updateCrmStatus(payload);
    }

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: true }));
  } catch (err) {
    console.error(err);
    res.writeHead(500, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: false, error: String(err) }));
  }
});

server.listen(PORT, () => {
  console.log(`DocuSeal webhook: http://127.0.0.1:${PORT}/api/webhooks/docuseal`);
});
