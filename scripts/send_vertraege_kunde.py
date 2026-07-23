#!/usr/bin/env python3
"""Kundenpaket senden: Prefill + Webschmiede-Signatur vorausfüllen + Kunden-Link.

Beispiel:
  python scripts/send_vertraege_kunde.py --firma "Snack House" --email kunde@example.de --setup 998 --monat 298

Optional: --angebot  |  --no-email  |  --dry-run
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

SIG_PATH = ROOT / "docs" / "agency" / "vertraege" / "assets" / "unterschrift-christian.png"
OUT_STATUS = ROOT / "docs" / "agency" / "vertraege" / "_last_send.json"

OWNER_CMD = r"""python3 -c "from pathlib import Path;import re
for p in [Path('/root/app/backend/.env'),Path('/root/app/deploy.secrets.local')]:
 t=p.read_text() if p.exists() else ''
 for k in ['AGENCY_OWNER_EMAIL','AGENCY_SMTP_FROM']:
  m=re.search(rf'^{k}=(.*)$',t,re.M)
  if m and m.group(1).strip():
   print(m.group(1).strip()); raise SystemExit"
"""

RUBY = r'''
require "json"
require "base64"

cfg = JSON.parse(File.read("/tmp/ws_send_cfg.json"))
external_id = cfg["external_id"]
kunde_email = cfg["kunde_email"]
owner_email = cfg["owner_email"]
values = cfg["values"]
sig_b64 = cfg["sig_b64"].to_s
send_email = cfg["send_email"]

user = User.first
raise "no user" unless user
template = Template.find_by!(external_id: external_id, account_id: user.account_id)

ws_uuid = template.submitters.find { |s| s["name"] == "Webschmiede" }["uuid"]
kunde_uuid = template.submitters.find { |s| s["name"] == "Kunde" }["uuid"]

ws_by_name = {}
kunde_by_name = {}
template.fields.each do |f|
  name = f["name"].to_s
  next if name.empty?
  raw = values[name]
  next if raw.nil? || raw.to_s.empty?
  if f["submitter_uuid"] == ws_uuid
    ws_by_name[name] = raw
  elsif f["submitter_uuid"] == kunde_uuid
    kunde_by_name[name] = raw
  end
end

# Signatur: Base64-PNG (alle Webschmiede-Signaturfelder)
template.fields.each do |f|
  next unless f["submitter_uuid"] == ws_uuid
  next unless f["type"] == "signature"
  next unless f["name"].to_s.include?("Webschmiede")
  ws_by_name[f["name"]] = "data:image/png;base64,#{sig_b64}"
end

# Datum Webschmiede falls leer
template.fields.each do |f|
  next unless f["submitter_uuid"] == ws_uuid
  next unless f["name"].to_s.include?("Datum Webschmiede")
  ws_by_name[f["name"]] ||= Date.current.to_s
end

ws_norm, ws_attachments, = Submitters::NormalizeValues.call(
  template, ws_by_name, submitter_name: "Webschmiede", purpose: :api, throw_errors: false
)
kunde_norm, kunde_attachments, = Submitters::NormalizeValues.call(
  template, kunde_by_name, submitter_name: "Kunde", purpose: :api, throw_errors: false
)

begin
  submissions = Submissions.create_from_submitters(
    template: template,
    user: user,
    submissions_attrs: [{
      submitters: [
        ActiveSupport::HashWithIndifferentAccess.new(
          name: "Webschmiede",
          email: owner_email,
          values: ws_norm
        ),
        ActiveSupport::HashWithIndifferentAccess.new(
          name: "Kunde",
          email: kunde_email,
          values: kunde_norm
        )
      ]
    }],
    source: :api,
    submitters_order: "preserved",
    params: ActiveSupport::HashWithIndifferentAccess.new("send_email" => false)
  )
rescue => e
  puts "ERR_CREATE=#{e.class}: #{e.message}"
  puts e.backtrace.first(12).join("\n")
  raise
end

submission = Array.wrap(submissions).first
if submission.nil?
  puts "ERR=submission nil submissions=#{submissions.inspect} ws_norm_keys=#{ws_norm.keys.size} kunde_norm_keys=#{kunde_norm.keys.size}"
  raise "submission nil"
end

ws = submission.submitters.find { |s| s.uuid == ws_uuid } || submission.submitters.find { |s| s.name == "Webschmiede" }
kunde = submission.submitters.find { |s| s.uuid == kunde_uuid } || submission.submitters.find { |s| s.name == "Kunde" }
raise "submitters missing ws=#{submission.submitters.map { |s| [s.uuid, s.name, s.email] }}" unless ws && kunde

(ws_attachments.to_a + kunde_attachments.to_a).each do |att|
  if ws_norm.value?(att.uuid)
    att.record = ws
  elsif kunde_norm.value?(att.uuid)
    att.record = kunde
  else
    att.record ||= ws
  end
  att.save! if att.changed? || att.new_record?
end

ws.values = ws.values.merge(ws_norm)
ws.completed_at = Time.current
ws.email = owner_email if ws.email.blank?
ws.name = "Webschmiede" if ws.name.blank?
ws.save!

kunde.values = kunde.values.merge(kunde_norm) if kunde_norm.present?
kunde.email = kunde_email if kunde.email.blank?
kunde.name = "Kunde" if kunde.name.blank?
kunde.save!

begin
  ProcessSubmitterCompletionJob.perform_async("submitter_id" => ws.id, "is_last" => false)
rescue StandardError => e
  puts "completion_job_err=#{e.class}: #{e.message}"
end

if send_email
  Submissions.send_signature_requests([submission])
else
  kunde.update!(sent_at: Time.current) if kunde.sent_at.blank?
end

base = "https://sign.digitalehandwerkskunst.de"
out = {
  submission_id: submission.id,
  submission_slug: submission.slug,
  template: template.name,
  external_id: external_id,
  kunde_email: kunde_email,
  kunde_link: "#{base}/s/#{kunde.slug}",
  webschmiede_completed: ws.reload.completed_at.present?,
  ws_value_count: ws.values.size,
  kunde_value_count: kunde.values.size,
  ws_value_keys: ws_by_name.keys,
  kunde_value_keys: kunde_by_name.keys,
  email_sent: send_email
}
puts out.to_json
'''


def build_values(args: argparse.Namespace) -> dict[str, str]:
    today = args.datum or date.today().isoformat()
    aufnr = args.auftragsnummer or f"WS-{date.today().strftime('%Y%m%d')}"
    paket = args.paket or "Gastro Bestell-System"
    setup = f"{int(args.setup)} EUR"
    monat = f"{int(args.monat)} EUR"
    adresse = args.adresse or ""
    values = {
        "Firma": args.firma,
        "Adresse": adresse,
        "Strasse": adresse,
        "PLZ Ort": args.plz_ort or "",
        "Vertreter": args.vertreter or "",
        "Funktion": args.funktion or "Inhaber",
        "Email": args.email,
        "Telefon": args.telefon or "",
        "USt-Id": args.ust_id or "",
        "Auftragsnummer": aufnr,
        "Angebotsnummer": aufnr.replace("WS-", "A-", 1),
        "Auftragsdatum": today,
        "Angebotsdatum": today,
        "Datum Webschmiede": today,
        "Paket": paket,
        "Setup Preis": setup,
        "Monat Preis": monat,
        "Laufzeit": str(args.laufzeit),
        "Kuendigungsfrist": str(args.kuendigung),
        "Zahlungsziel": str(args.zahlungsziel),
        "Gueltig bis": args.gueltig_bis or "",
        "Enthalten": args.enthalten or "Portal, Admin, Hosting laut Paket",
        "Nicht enthalten": args.nicht_enthalten
        or "Werbebudget, Hardware, Rechts-/Steuerberatung",
        "Auftrag Auftragsnummer": aufnr,
        "Auftrag Auftragsdatum": today,
        "Auftrag Paket": paket,
        "Auftrag Setup Preis": setup,
        "Auftrag Monat Preis": monat,
        "Auftrag Laufzeit": str(args.laufzeit),
        "Auftrag Kuendigungsfrist": str(args.kuendigung),
        "Auftrag Zahlungsziel": str(args.zahlungsziel),
        "AVV AVV Nummer": f"AVV-{aufnr}",
        "AVV Leistungen": paket,
    }
    return {k: v for k, v in values.items() if v not in ("", None)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Webschmiede Vertrags-Paket an Kunden senden")
    ap.add_argument("--firma", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--vertreter", default="")
    ap.add_argument("--adresse", default="")
    ap.add_argument("--plz-ort", default="")
    ap.add_argument("--telefon", default="")
    ap.add_argument("--ust-id", default="")
    ap.add_argument("--funktion", default="Inhaber")
    ap.add_argument("--paket", default="Gastro Bestell-System")
    ap.add_argument("--setup", type=float, default=998)
    ap.add_argument("--monat", type=float, default=298)
    ap.add_argument("--laufzeit", type=int, default=12)
    ap.add_argument("--kuendigung", type=int, default=1)
    ap.add_argument("--zahlungsziel", type=int, default=14)
    ap.add_argument("--auftragsnummer", default="")
    ap.add_argument("--datum", default="")
    ap.add_argument("--gueltig-bis", default="")
    ap.add_argument("--enthalten", default="")
    ap.add_argument("--nicht-enthalten", default="")
    ap.add_argument("--angebot", action="store_true")
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not SIG_PATH.exists():
        raise SystemExit(f"Signatur fehlt: {SIG_PATH}")

    external_id = "ws-angebot" if args.angebot else "ws-kundenpaket"
    values = build_values(args)

    if args.dry_run:
        print(json.dumps({"external_id": external_id, "values": values}, indent=2, ensure_ascii=False))
        return 0

    c = paramiko.SSHClient()
    ssh_connect(c, timeout=30, banner_timeout=30, role="web")
    _, o, _ = c.exec_command(OWNER_CMD, timeout=20)
    owner = o.read().decode().strip() or "info@digitalehandwerkskunst.de"

    cfg = {
        "external_id": external_id,
        "kunde_email": args.email,
        "owner_email": owner,
        "values": values,
        "sig_b64": base64.b64encode(SIG_PATH.read_bytes()).decode("ascii"),
        "send_email": not args.no_email,
    }

    sftp = c.open_sftp()
    with sftp.file("/tmp/ws_send_cfg.json", "w") as f:
        f.write(json.dumps(cfg))
    with sftp.file("/tmp/ws_send_kunde.rb", "w") as f:
        f.write(RUBY)
    sftp.close()

    cmd = (
        "docker cp /tmp/ws_send_cfg.json docuseal-docuseal-1:/tmp/ws_send_cfg.json && "
        "docker cp /tmp/ws_send_kunde.rb docuseal-docuseal-1:/tmp/ws_send_kunde.rb && "
        "cd /opt/docuseal && docker compose exec -T -w /app docuseal "
        "bundle exec rails runner /tmp/ws_send_kunde.rb 2>&1"
    )
    _, o, e = c.exec_command(cmd, timeout=240)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    c.close()

    print(out[-4000:])
    result = None
    for ln in reversed(out.splitlines()):
        s = ln.strip()
        if s.startswith("{") and "kunde_link" in s:
            try:
                result = json.loads(s)
                break
            except json.JSONDecodeError:
                continue
    if not result:
        OUT_STATUS.write_text(out, encoding="utf-8")
        print("Send fehlgeschlagen")
        return 1

    OUT_STATUS.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\nKunden-Link:", result.get("kunde_link"))
    print("Webschmiede completed:", result.get("webschmiede_completed"))
    print("Status:", OUT_STATUS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
