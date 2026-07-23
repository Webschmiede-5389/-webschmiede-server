#!/usr/bin/env python3
"""Import workorders n8n workflow + smoke one order on web."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import paramiko
from agency_config import ssh_connect

LOCAL = ROOT / "infra" / "n8n" / "workflow-workorders.json"
NAME = "Agency – Workorders Bridge"
REMOTE = "/tmp/n8n-workorders"


def run(c, cmd, timeout=120):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode(errors="replace")


def main():
    auto = paramiko.SSHClient()
    ssh_connect(auto, timeout=20, banner_timeout=20, role="auto")
    run(auto, f"mkdir -p {REMOTE}")
    sftp = auto.open_sftp()
    sftp.put(str(LOCAL), f"{REMOTE}/{LOCAL.name}")
    sftp.close()
    print(run(auto, f"export $(grep -v '^#' /opt/n8n/.env | xargs) && N8N_USER_FOLDER=/opt/n8n/data n8n import:workflow --separate --input={REMOTE} 2>&1")[:500])
    act = f"""
import sqlite3
conn=sqlite3.connect('/opt/n8n/data/.n8n/database.sqlite')
want={NAME!r}
for wid,name,active in conn.execute('SELECT id,name,active FROM workflow_entity'):
    if name==want:
        conn.execute('UPDATE workflow_entity SET active=1 WHERE id=?',(wid,))
        print('ON', name)
conn.commit(); conn.close()
"""
    sftp = auto.open_sftp()
    with sftp.file("/tmp/n8n_wo.py", "w") as f:
        f.write(act)
    sftp.close()
    print(run(auto, "python3 /tmp/n8n_wo.py; systemctl restart n8n; sleep 2; systemctl is-active n8n"))
    auto.close()

    web = paramiko.SSHClient()
    ssh_connect(web, timeout=20, banner_timeout=20, role="web")
    print(run(web, r"""
cd /root/app/backend
/root/app/venv/bin/python - <<'PY'
import os, sqlite3
from pathlib import Path
for line in Path('/root/app/backend/.env').read_text(errors='replace').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k,v=line.split('=',1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
import agency_workorders as wo
db=sqlite3.connect('/root/app/backend/orders.db'); db.row_factory=sqlite3.Row
r=wo.handle_message(db, 'SHY001 Notiz: Workorder-Smoke Test Telegram', source='smoke')
db.commit()
print(r.get('route'), r.get('executed'), (r.get('reply') or '')[:200])
# tg notice
import json, urllib.request
vals={}
for line in Path('/root/app/backend/.env').read_text(errors='replace').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k,v=line.split('=',1); vals[k.strip()]=v.strip().strip('"').strip("'")
text='Auftraege live.\nBeispiel: SHY001 Tisch-Promo auf Erste Bestellung 10%\nWebsite-Umbau: Auftrag: Hero kuerzer machen\nDashboard: https://digitalehandwerkskunst.de/workorders.html'
payload=json.dumps({'chat_id':vals.get('TELEGRAM_OWNER_CHAT_ID','').split(',')[0],'text':text}).encode()
req=urllib.request.Request(f"https://api.telegram.org/bot{vals.get('TELEGRAM_BOT_TOKEN')}/sendMessage", data=payload, headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req, timeout=20) as resp:
    print('tg', json.loads(resp.read().decode()).get('ok'))
db.close()
PY
"""))
    web.close()


if __name__ == "__main__":
    main()
