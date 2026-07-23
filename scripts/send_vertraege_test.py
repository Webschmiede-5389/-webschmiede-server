#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paramiko
from agency_config import ssh_connect

OWNER_CMD = r"""python3 -c "from pathlib import Path;import re
for p in [Path('/root/app/backend/.env'),Path('/root/app/deploy.secrets.local')]:
 t=p.read_text() if p.exists() else ''
 for k in ['AGENCY_OWNER_EMAIL','AGENCY_SMTP_FROM']:
  m=re.search(rf'^{k}=(.*)$',t,re.M)
  if m and m.group(1).strip():
   print(m.group(1).strip()); raise SystemExit"
"""


def main() -> int:
    c = paramiko.SSHClient()
    ssh_connect(c, timeout=25, banner_timeout=25, role="web")
    _, o, _ = c.exec_command(OWNER_CMD, timeout=20)
    owner = o.read().decode().strip()
    print("owner_len", len(owner))

    ruby = (
        "begin\n"
        f"  email = {json.dumps(owner)}\n"
        "  user = User.first\n"
        '  template = Template.find_by!(external_id: "ws-auftrag")\n'
        "  puts \"template_id=#{template.id}\"\n"
        "  submissions_attrs = [{ submitters: [{ 'name' => 'Kunde', 'email' => email }, { 'name' => 'Webschmiede', 'email' => email }] }]\n"
        "  submissions = Submissions.create_from_submitters(\n"
        "    template: template, user: user, submissions_attrs: submissions_attrs, source: :invite,\n"
        "    params: { 'send_email' => true, 'order' => 'preserved' }\n"
        "  )\n"
        "  puts \"created=#{Array.wrap(submissions).map(&:id)}\"\n"
        "  Submissions.send_signature_requests(Array.wrap(submissions))\n"
        "  Array.wrap(submissions).each do |submission|\n"
        "    puts({ id: submission.id, slug: submission.slug, submitters: submission.submitters.order(:id).map { |s| { name: s.name, sent: !s.sent_at.nil? } } }.to_json)\n"
        "  end\n"
        "rescue => e\n"
        "  puts \"ERR=#{e.class}: #{e.message}\"\n"
        "  puts e.backtrace.first(8).join(\"\\n\")\n"
        "end\n"
    )

    sftp = c.open_sftp()
    with sftp.file("/tmp/ws_send.rb", "w") as f:
        f.write(ruby)
    sftp.close()

    cmd = (
        "docker cp /tmp/ws_send.rb docuseal-docuseal-1:/tmp/ws_send.rb && "
        "cd /opt/docuseal && docker compose exec -T -w /app docuseal "
        "bundle exec rails runner /tmp/ws_send.rb 2>&1"
    )
    _, o, e = c.exec_command(cmd, timeout=180)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    print(out[-3000:])
    Path("docs/agency/vertraege/_send_test.txt").write_text(out, encoding="utf-8")
    c.close()
    return 0 if "ERR=" not in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
