#!/usr/bin/env python3
"""Create DocuSeal templates from PDFs via Rails (Community, kein Pro-API).

Einzelvorlagen + Kundenpaket (Auftrag + AGB + AVV in einer Vorlage).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

PDF_DIR = ROOT / "docs" / "agency" / "vertraege" / "pdf"
REMOTE_DIR = "/tmp/ws-vertraege"

# Einzel-PDFs die hochgeladen werden
PDF_FILES = [
    "01-angebot.pdf",
    "02-auftrag.pdf",
    "03-agb.pdf",
    "04-avv.pdf",
]

RUBY = r'''
require "securerandom"

user = User.first
raise "no user" unless user
account = user.account
folder = TemplateFolders.find_or_create_by_name(user, "Webschmiede Verträge")

SINGLE = {
  "ws-angebot" => [["/data/ws-vertraege/01-angebot.pdf"], "WS Angebot"],
  "ws-auftrag" => [["/data/ws-vertraege/02-auftrag.pdf"], "WS Auftrag Dienstleistung"],
  "ws-agb" => [["/data/ws-vertraege/03-agb.pdf"], "WS AGB B2B"],
  "ws-avv" => [["/data/ws-vertraege/04-avv.pdf"], "WS AVV Auftragsverarbeitung"],
  "ws-kundenpaket" => [
    [
      "/data/ws-vertraege/02-auftrag.pdf",
      "/data/ws-vertraege/03-agb.pdf",
      "/data/ws-vertraege/04-avv.pdf"
    ],
    "WS Kundenpaket Auftrag AGB AVV"
  ],
}

def ws_field?(fname)
  fname.include?("Webschmiede") ||
    fname.end_with?(" WS") ||
    fname.include?("Angebotsnummer") ||
    fname.include?("Auftragsnummer") ||
    fname.include?("Setup") ||
    fname.include?("Monat") ||
    fname.include?("Paket") ||
    fname.include?("Laufzeit") ||
    fname.include?("Kuendigung") ||
    fname.include?("Enthalten") ||
    fname.include?("Nicht enthalten") ||
    fname.include?("Gueltig") ||
    fname.include?("Angebotsdatum") ||
    fname.include?("Auftragsdatum") ||
    fname.include?("Zahlungsziel") ||
    fname.include?("AVV Nummer") ||
    fname.include?("Leistungen")
end

def assign_roles!(fields, kunde_uuid, ws_uuid)
  fields.map do |f|
    fname = f["name"].to_s
    f = f.deep_dup
    if fname.include?("Unterschrift")
      f["type"] = "signature"
      f["required"] = true
    end
    if ws_field?(fname)
      f["submitter_uuid"] = ws_uuid
    else
      f["submitter_uuid"] = kunde_uuid
    end
    if fname.include?("Datum Webschmiede")
      f["submitter_uuid"] = ws_uuid
      f["type"] = "date"
    elsif fname.include?("Datum Kunde")
      f["submitter_uuid"] = kunde_uuid
      f["type"] = "date"
    end
    f
  end
end

results = []

SINGLE.each do |external_id, (paths, name)|
  paths.each { |p| raise "missing #{p}" unless File.exist?(p) }

  template = Template.find_by(external_id: external_id, account_id: account.id)
  if template
    template.documents.destroy_all
    template.update!(name: name, folder: folder, fields: [], schema: [], archived_at: nil)
  else
    template = Template.new(
      account: account,
      author: user,
      folder: folder,
      source: :api,
      name: name,
      external_id: external_id,
      fields: [],
      schema: [],
      shared_link: true
    )
    Templates.maybe_assign_access(template)
    template.save!
  end

  files = paths.map do |path|
    ActionDispatch::Http::UploadedFile.new(
      tempfile: File.open(path, "rb"),
      filename: File.basename(path),
      type: "application/pdf"
    )
  end

  documents, = Templates::CreateAttachments.call(template, { files: files }, extract_fields: true)
  schema = documents.map { |doc| { "attachment_uuid" => doc.uuid, "name" => doc.filename.base } }

  fields = Templates::ProcessDocument.normalize_attachment_fields(template, documents)

  # Bei Mehrfach-Docs: Feldnamen pro Dokument eindeutig machen (außer Signaturen/Daten geteilt ok)
  if documents.size > 1
    uuid_to_label = {}
    documents.each_with_index do |doc, idx|
      label = case doc.filename.base
              when /auftrag/i then "Auftrag"
              when /agb/i then "AGB"
              when /avv/i then "AVV"
              else "Dok#{idx + 1}"
              end
      uuid_to_label[doc.uuid] = label
    end
    fields = fields.map do |f|
      f = f.deep_dup
      areas = Array.wrap(f["areas"])
      att = areas.first && areas.first["attachment_uuid"]
      label = uuid_to_label[att]
      base = f["name"].to_s
      next f if base.empty? || label.nil?
      # Prefill-freundliche Namen: gemeinsame Kundendaten ohne Prefix behalten
      shared = %w[Firma Adresse Vertreter Funktion Email Telefon USt-Id Strasse PLZ\ Ort]
      if shared.include?(base) || base.start_with?("Unterschrift") || base.start_with?("Datum ")
        f
      else
        f["name"] = "#{label} #{base}"
        f
      end
    end
  end

  kunde_uuid = SecureRandom.uuid
  ws_uuid = SecureRandom.uuid
  # Reihenfolge: erst Webschmiede (vorausgefüllt), dann Kunde
  template.submitters = [
    { "name" => "Webschmiede", "uuid" => ws_uuid },
    { "name" => "Kunde", "uuid" => kunde_uuid }
  ]

  fields = assign_roles!(fields, kunde_uuid, ws_uuid)

  template.update!(schema: schema, fields: fields)
  WebhookUrls.enqueue_events(template, "template.created")
  SearchEntries.enqueue_reindex(template)

  results << {
    external_id: external_id,
    id: template.id,
    name: template.name,
    slug: template.slug,
    fields: template.fields.size,
    signatures: template.fields.count { |f| f["type"] == "signature" },
    documents: documents.size,
    submitters: template.submitters.map { |s| s["name"] }
  }
end

puts results.to_json
'''


def main() -> int:
    for fn in PDF_FILES:
        if not (PDF_DIR / fn).exists():
            raise SystemExit(f"PDF fehlt: {fn}")

    c = paramiko.SSHClient()
    ssh_connect(c, timeout=30, banner_timeout=30, role="web")
    sftp = c.open_sftp()
    try:
        try:
            sftp.mkdir(REMOTE_DIR)
        except OSError:
            pass
        for fn in PDF_FILES:
            sftp.put(str(PDF_DIR / fn), f"{REMOTE_DIR}/{fn}")
            print("uploaded", fn)
        with sftp.file("/tmp/ws_create_templates.rb", "w") as f:
            f.write(RUBY)
    finally:
        sftp.close()

    cmds = [
        "docker exec docuseal-docuseal-1 rm -rf /data/ws-vertraege && docker exec docuseal-docuseal-1 mkdir -p /data/ws-vertraege",
        f"docker cp {REMOTE_DIR}/. docuseal-docuseal-1:/data/ws-vertraege/",
        "docker cp /tmp/ws_create_templates.rb docuseal-docuseal-1:/tmp/ws_create_templates.rb",
        "cd /opt/docuseal && docker compose exec -T -w /app docuseal bundle exec rails runner /tmp/ws_create_templates.rb",
    ]
    out_all = ""
    for cmd in cmds:
        print(">>>", cmd[:100])
        _, o, e = c.exec_command(cmd, timeout=300)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        print(out[-3000:] if len(out) > 3000 else out)
        if err.strip():
            print(err[-1500:])
        out_all += out

    c.close()

    lines = [ln for ln in out_all.splitlines() if ln.strip().startswith("[")]
    if not lines:
        print("Kein JSON-Ergebnis")
        return 1
    data = json.loads(lines[-1])
    status = {
        "via": "rails-community",
        "folder": "Webschmiede Verträge",
        "templates": data,
        "dashboard": "https://sign.digitalehandwerkskunst.de/templates",
    }
    path = ROOT / "docs" / "agency" / "vertraege" / "docuseal-status.json"
    path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Status", path)
    for t in data:
        print(
            f"OK {t['name']} id={t['id']} fields={t['fields']} docs={t.get('documents', 1)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
