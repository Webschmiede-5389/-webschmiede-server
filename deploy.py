"""
Deploy: backend + alle static files → web-01 (nach CX33-Cutover)
"""
import paramiko, os, sys
from agency_config import ssh_connect, target_secrets

_secrets = target_secrets("web")
HOST = _secrets["SERVER_HOST"]
USER = _secrets["SERVER_USER"]

LOCAL_BASE  = os.path.join(os.path.dirname(__file__), 'app')
REMOTE_APP  = '/root/app'
WEBROOT     = '/var/www/snackhouse-mechernich'

FILES = [
    (r'backend\auth_users.py', f'{REMOTE_APP}/backend/auth_users.py'),
    (r'backend\main.py',        f'{REMOTE_APP}/backend/main.py'),
    (r'backend\order_validation.py', f'{REMOTE_APP}/backend/order_validation.py'),
    (r'backend\loyalty.py',        f'{REMOTE_APP}/backend/loyalty.py'),
    (r'backend\seminars.py',       f'{REMOTE_APP}/backend/seminars.py'),
    (r'static\order.html',      f'{REMOTE_APP}/static/order.html'),
    (r'static\admin.html',      f'{REMOTE_APP}/static/admin.html'),
    (r'static\anfrage.html',    f'{REMOTE_APP}/static/anfrage.html'),
    (r'static\seminare.html',   f'{REMOTE_APP}/static/seminare.html'),
    (r'static\agency.html',     f'{REMOTE_APP}/static/agency.html'),
    (r'static\agency-auth.js',  f'{REMOTE_APP}/static/agency-auth.js'),
    (r'data\kalkulator-preise.json', f'{REMOTE_APP}/data/kalkulator-preise.json'),
    (r'static\angebote.html',  f'{REMOTE_APP}/static/angebote.html'),
    (r'static\angebote.json',   f'{REMOTE_APP}/static/angebote.json'),
    (r'static\agency-hub.html', f'{REMOTE_APP}/static/agency-hub.html'),
    (r'static\nils.html', f'{REMOTE_APP}/static/nils.html'),
    (r'static\jay.html', f'{REMOTE_APP}/static/jay.html'),
    (r'backend\jay_voice.py', f'{REMOTE_APP}/backend/jay_voice.py'),
    (r'static\agency-keys.html', f'{REMOTE_APP}/static/agency-keys.html'),
    (r'static\agency-setup.html', f'{REMOTE_APP}/static/agency-setup.html'),
    (r'static\onboarding.html', f'{REMOTE_APP}/static/onboarding.html'),
    (r'static\uebergabe-handbuch.html', f'{REMOTE_APP}/static/uebergabe-handbuch.html'),
    (r'backend\onboarding.py', f'{REMOTE_APP}/backend/onboarding.py'),
    (r'backend\client_brand.py', f'{REMOTE_APP}/backend/client_brand.py'),
    (r'backend\domain_onboarding.py', f'{REMOTE_APP}/backend/domain_onboarding.py'),
    (r'backend\google_onboarding.py', f'{REMOTE_APP}/backend/google_onboarding.py'),
    (r'backend\agency_packages.py', f'{REMOTE_APP}/backend/agency_packages.py'),
    (r'backend\stripe_billing.py', f'{REMOTE_APP}/backend/stripe_billing.py'),
    (r'backend\provision.py', f'{REMOTE_APP}/backend/provision.py'),
    (r'backend\inbox_agent.py', f'{REMOTE_APP}/backend/inbox_agent.py'),
    (r'backend\nightly_watchdog.py', f'{REMOTE_APP}/backend/nightly_watchdog.py'),
    (r'backend\resource_watchdog.py', f'{REMOTE_APP}/backend/resource_watchdog.py'),
    (r'backend\agency_secrets.py', f'{REMOTE_APP}/backend/agency_secrets.py'),
    (r'backend\tourmeter_fuel.py', f'{REMOTE_APP}/backend/tourmeter_fuel.py'),
    (r'backend\messaging.py', f'{REMOTE_APP}/backend/messaging.py'),
    (r'backend\push_notifications.py', f'{REMOTE_APP}/backend/push_notifications.py'),
    (r'backend\whatsapp_tenant.py', f'{REMOTE_APP}/backend/whatsapp_tenant.py'),
    (r'backend\whatsapp_embedded.py', f'{REMOTE_APP}/backend/whatsapp_embedded.py'),
    (r'backend\whatsapp_webhook.py', f'{REMOTE_APP}/backend/whatsapp_webhook.py'),
    (r'backend\nils_ops.py', f'{REMOTE_APP}/backend/nils_ops.py'),
    (r'backend\nils_whatsapp_ops.py', f'{REMOTE_APP}/backend/nils_whatsapp_ops.py'),
    (r'backend\telegram_ops.py', f'{REMOTE_APP}/backend/telegram_ops.py'),
    (r'backend\telegram_session.py', f'{REMOTE_APP}/backend/telegram_session.py'),
    (r'backend\telegram_memory.py', f'{REMOTE_APP}/backend/telegram_memory.py'),
    (r'backend\nils_tools.py', f'{REMOTE_APP}/backend/nils_tools.py'),
    (r'backend\nils_cursor_bridge.py', f'{REMOTE_APP}/backend/nils_cursor_bridge.py'),
    (r'backend\nils_orchestrator.py', f'{REMOTE_APP}/backend/nils_orchestrator.py'),
    (r'backend\nils_truth.py', f'{REMOTE_APP}/backend/nils_truth.py'),
    (r'backend\nils_research.py', f'{REMOTE_APP}/backend/nils_research.py'),
    (r'backend\nils_inventory.py', f'{REMOTE_APP}/backend/nils_inventory.py'),
    (r'backend\nils_git_deploy.py', f'{REMOTE_APP}/backend/nils_git_deploy.py'),
    (r'backend\nils_cost_sentry.py', f'{REMOTE_APP}/backend/nils_cost_sentry.py'),
    (r'backend\nils_daily_report.py', f'{REMOTE_APP}/backend/nils_daily_report.py'),
    (r'backend\nils_discovery.py', f'{REMOTE_APP}/backend/nils_discovery.py'),
    (r'backend\nils_eta.py', f'{REMOTE_APP}/backend/nils_eta.py'),
    (r'backend\nils_brain_watch.py', f'{REMOTE_APP}/backend/nils_brain_watch.py'),
    (r'backend\nils_ux_gate.py', f'{REMOTE_APP}/backend/nils_ux_gate.py'),
    (r'backend\nils_guided.py', f'{REMOTE_APP}/backend/nils_guided.py'),
    (r'backend\llm_client.py', f'{REMOTE_APP}/backend/llm_client.py'),
    (r'backend\nils_dispatcher.py', f'{REMOTE_APP}/backend/nils_dispatcher.py'),
    (r'backend\requesty_client.py', f'{REMOTE_APP}/backend/requesty_client.py'),
    (r'backend\llm_web.py', f'{REMOTE_APP}/backend/llm_web.py'),
    (r'backend\telegram_agent.py', f'{REMOTE_APP}/backend/telegram_agent.py'),
    (r'backend\agency_workorders.py', f'{REMOTE_APP}/backend/agency_workorders.py'),
    (r'backend\human_voice.py', f'{REMOTE_APP}/backend/human_voice.py'),
    (r'static\workorders.html', f'{REMOTE_APP}/static/workorders.html'),
    (r'backend\requirements.txt', f'{REMOTE_APP}/backend/requirements.txt'),
    (r'backend\agency_mail.py', f'{REMOTE_APP}/backend/agency_mail.py'),
    (r'backend\agency_cockpit.py', f'{REMOTE_APP}/backend/agency_cockpit.py'),
    (r'backend\client_setup.py', f'{REMOTE_APP}/backend/client_setup.py'),
    (r'backend\agency_chat.py', f'{REMOTE_APP}/backend/agency_chat.py'),
    (r'backend\agency_router.py', f'{REMOTE_APP}/backend/agency_router.py'),
    (r'backend\agency_router_security.py', f'{REMOTE_APP}/backend/agency_router_security.py'),
    (r'backend\agency_brain.py', f'{REMOTE_APP}/backend/agency_brain.py'),
    (r'backend\agency_radar.py', f'{REMOTE_APP}/backend/agency_radar.py'),
    (r'backend\agency_shipcheck.py', f'{REMOTE_APP}/backend/agency_shipcheck.py'),
    (r'backend\ops_guardian.py', f'{REMOTE_APP}/backend/ops_guardian.py'),
    (r'backend\dual_infra.py', f'{REMOTE_APP}/backend/dual_infra.py'),
    (r'backend\agency_stefan.py', f'{REMOTE_APP}/backend/agency_stefan.py'),
    (r'backend\agency_anwalt.py', f'{REMOTE_APP}/backend/agency_anwalt.py'),
    (r'backend\agency_scout.py', f'{REMOTE_APP}/backend/agency_scout.py'),
    (r'backend\agency_commander.py', f'{REMOTE_APP}/backend/agency_commander.py'),
    (r'backend\b2b_portal.py', f'{REMOTE_APP}/backend/b2b_portal.py'),
    (r'backend\b2b_baustoff.py', f'{REMOTE_APP}/backend/b2b_baustoff.py'),
    (r'backend\buchhaltung_onboarding.py', f'{REMOTE_APP}/backend/buchhaltung_onboarding.py'),
    (r'backend\sales_pipeline.py', f'{REMOTE_APP}/backend/sales_pipeline.py'),
    (r'backend\sales_companion.py', f'{REMOTE_APP}/backend/sales_companion.py'),
    (r'backend\agency_packages.py', f'{REMOTE_APP}/backend/agency_packages.py'),
    (r'static\b2b-portal.html', f'{REMOTE_APP}/static/b2b-portal.html'),
    (r'static\buchhaltung-onboarding.html', f'{REMOTE_APP}/static/buchhaltung-onboarding.html'),
    (r'static\sales-dashboard.html', f'{REMOTE_APP}/static/sales-dashboard.html'),
    (r'static\sales-angebot.html', f'{REMOTE_APP}/static/sales-angebot.html'),
    (r'backend\agency_leads.py', f'{REMOTE_APP}/backend/agency_leads.py'),
    (r'backend\agency_akquise.py', f'{REMOTE_APP}/backend/agency_akquise.py'),
    (r'..\akquise\register.py', f'{REMOTE_APP}/akquise/register.py'),
    (r'..\akquise\__init__.py', f'{REMOTE_APP}/akquise/__init__.py'),
    (r'backend\agency_metrics.py', f'{REMOTE_APP}/backend/agency_metrics.py'),
    (r'backend\agency_ops.py', f'{REMOTE_APP}/backend/agency_ops.py'),
    (r'backend\jobs.py',           f'{REMOTE_APP}/backend/jobs.py'),
    (r'backend\bookkeeping.py', f'{REMOTE_APP}/backend/bookkeeping.py'),
    (r'backend\integrations\__init__.py', f'{REMOTE_APP}/backend/integrations/__init__.py'),
    (r'backend\integrations\lexware.py', f'{REMOTE_APP}/backend/integrations/lexware.py'),
    (r'backend\integrations\inwx.py', f'{REMOTE_APP}/backend/integrations/inwx.py'),
    (r'backend\email_templates.py', f'{REMOTE_APP}/backend/email_templates.py'),
    (r'..\kunden_ids.py', f'{REMOTE_APP}/kunden_ids.py'),
    (r'..\kunden_ids.py', f'{REMOTE_APP}/backend/kunden_ids.py'),
    (r'..\n8n_kunde.py', f'{REMOTE_APP}/n8n_kunde.py'),
    (r'static\akquise-report.html', f'{REMOTE_APP}/static/akquise-report.html'),
    (r'static\transport-kalkulator.html', f'{REMOTE_APP}/static/transport-kalkulator.html'),
    (r'static\transport-kalkulator.webmanifest', f'{REMOTE_APP}/static/transport-kalkulator.webmanifest'),
    (r'static\transport-kalkulator-sw.js', f'{REMOTE_APP}/static/transport-kalkulator-sw.js'),
    (r'static\tourmeter-mark.svg', f'{REMOTE_APP}/static/tourmeter-mark.svg'),
    (r'static\index.html',      f'{REMOTE_APP}/static/index.html'),
    (r'static\manifest.webmanifest', f'{REMOTE_APP}/static/manifest.webmanifest'),
    (r'static\sw.js',           f'{REMOTE_APP}/static/sw.js'),
    (r'static\order-push-sw.js', f'{REMOTE_APP}/static/order-push-sw.js'),
    (r'static\datenschutz.html',f'{REMOTE_APP}/static/datenschutz.html'),
    (r'static\impressum.html',  f'{REMOTE_APP}/static/impressum.html'),
    (r'static\favicon.png',     f'{REMOTE_APP}/static/favicon.png'),
    (r'static\favicon-192.png', f'{REMOTE_APP}/static/favicon-192.png'),
    (r'static\apple-touch-icon.png', f'{REMOTE_APP}/static/apple-touch-icon.png'),
]

JARVIS_FILES = [
    (r'jarvis\__init__.py',       f'{REMOTE_APP}/jarvis/__init__.py'),
    (r'jarvis\bot.py',            f'{REMOTE_APP}/jarvis/bot.py'),
    (r'jarvis\parser.py',         f'{REMOTE_APP}/jarvis/parser.py'),
    (r'jarvis\permissions.py',    f'{REMOTE_APP}/jarvis/permissions.py'),
    (r'jarvis\menu_catalog.json', f'{REMOTE_APP}/jarvis/menu_catalog.json'),
    (r'jarvis\menu_prices.json',  f'{REMOTE_APP}/jarvis/menu_prices.json'),
    (r'jarvis\inbox_faq.json',   f'{REMOTE_APP}/jarvis/inbox_faq.json'),
    (r'jarvis\knowledge.py',     f'{REMOTE_APP}/jarvis/knowledge.py'),
]

def run(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out.strip().encode('ascii','replace').decode())
    if err.strip(): print('ERR:', err.strip()[:400].encode('ascii','replace').decode())
    return out

print(f"Deploy-Ziel: {USER}@{HOST} (web-01)")
client = paramiko.SSHClient()
ssh_connect(client, timeout=15, banner_timeout=15, role="web")

run(client, f'mkdir -p {REMOTE_APP}/jarvis {REMOTE_APP}/kunden {REMOTE_APP}/uploads/menu {REMOTE_APP}/backend/integrations {REMOTE_APP}/data')

sftp = client.open_sftp()

LOCAL_ROOT  = os.path.dirname(LOCAL_BASE)
AGENCY_ROOT_FILES = [
    ("agency_email.py", f"{REMOTE_APP}/agency_email.py"),
]
KUNDEN_LOCAL = os.path.join(LOCAL_ROOT, 'kunden')

for local_rel, remote in FILES + JARVIS_FILES:
    local_path = os.path.join(LOCAL_BASE, local_rel)
    if not os.path.exists(local_path):
        print(f'SKIP (not found): {local_path}')
        continue
    print(f'Upload: {local_rel} -> {remote}')
    sftp.put(local_path, remote)

for fname, remote in AGENCY_ROOT_FILES:
    local_path = os.path.join(LOCAL_ROOT, fname)
    if os.path.exists(local_path):
        print(f'Upload: {fname} -> {remote}')
        sftp.put(local_path, remote)

_req_local = os.path.join(LOCAL_ROOT, 'requesty.secrets.local')
if os.path.isfile(_req_local):
    print('Upload: requesty.secrets.local -> /root/app/requesty.secrets.local')
    sftp.put(_req_local, f'{REMOTE_APP}/requesty.secrets.local')

_cur_local = os.path.join(LOCAL_ROOT, 'cursor.secrets.local')
if os.path.isfile(_cur_local):
    print('Upload: cursor.secrets.local -> /root/app/cursor.secrets.local')
    sftp.put(_cur_local, f'{REMOTE_APP}/cursor.secrets.local')

sftp.close()

# Knowledge Packs
KNOWLEDGE_LOCAL = os.path.join(LOCAL_ROOT, 'knowledge', 'packs')
if os.path.isdir(KNOWLEDGE_LOCAL):
    print('\nUpload knowledge/packs/*.json...')
    run(client, f'mkdir -p {REMOTE_APP}/knowledge/packs')
    sftp = client.open_sftp()
    for fname in os.listdir(KNOWLEDGE_LOCAL):
        if fname.endswith('.json'):
            local = os.path.join(KNOWLEDGE_LOCAL, fname)
            remote = f'{REMOTE_APP}/knowledge/packs/{fname}'
            print(f'Upload: knowledge/packs/{fname}')
            sftp.put(local, remote)
    sftp.close()

# Akquise-Reports fuer Scout-Queue (JSON)
AKQ_REPORTS = os.path.join(LOCAL_ROOT, 'docs', 'akquise', 'reports')
if os.path.isdir(AKQ_REPORTS):
    print('\nUpload docs/akquise/reports/*.json...')
    run(client, f'mkdir -p {REMOTE_APP}/docs/akquise/reports')
    sftp = client.open_sftp()
    for fname in os.listdir(AKQ_REPORTS):
        if fname.endswith('.json'):
            local = os.path.join(AKQ_REPORTS, fname)
            remote = f'{REMOTE_APP}/docs/akquise/reports/{fname}'
            print(f'Upload: docs/akquise/reports/{fname}')
            sftp.put(local, remote)
    sftp.close()

# CI-Vorlagen (Ordner static/ci/)
CI_LOCAL = os.path.join(LOCAL_BASE, 'static', 'ci')
if os.path.isdir(CI_LOCAL):
    print('\nUpload static/ci/...')
    sftp = client.open_sftp()
    run(client, f'mkdir -p {REMOTE_APP}/static/ci')
    for fname in os.listdir(CI_LOCAL):
        local = os.path.join(CI_LOCAL, fname)
        if os.path.isfile(local):
            remote = f'{REMOTE_APP}/static/ci/{fname}'
            print(f'Upload: static/ci/{fname}')
            sftp.put(local, remote)
    sftp.close()

# Kunden-Brand (Logo für Aufsteller etc.)
BRAND_LOCAL = os.path.join(LOCAL_BASE, 'static', 'brand')
if os.path.isdir(BRAND_LOCAL):
    print('\nUpload static/brand/...')
    sftp = client.open_sftp()
    run(client, f'mkdir -p {REMOTE_APP}/static/brand')
    for fname in os.listdir(BRAND_LOCAL):
        local = os.path.join(BRAND_LOCAL, fname)
        if os.path.isfile(local):
            remote = f'{REMOTE_APP}/static/brand/{fname}'
            print(f'Upload: static/brand/{fname}')
            sftp.put(local, remote)
    sftp.close()

# Kunden-JSON deployen
print('\nUpload kunden/*.json...')
run(client, f'mkdir -p {REMOTE_APP}/kunden {REMOTE_APP}/uploads/menu')
if os.path.isdir(KUNDEN_LOCAL):
    sftp = client.open_sftp()
    for fname in os.listdir(KUNDEN_LOCAL):
        if fname.endswith('.json'):
            local = os.path.join(KUNDEN_LOCAL, fname)
            remote = f'{REMOTE_APP}/kunden/{fname}'
            print(f'Upload: kunden/{fname}')
            sftp.put(local, remote)
    sftp.close()

# n8n Kunden-Vorlagen
N8N_KUNDE_LOCAL = os.path.join(os.path.dirname(__file__), 'infra', 'n8n', 'kunde')
if os.path.isdir(N8N_KUNDE_LOCAL):
    print('\nUpload infra/n8n/kunde/*.json...')
    run(client, f'mkdir -p {REMOTE_APP}/infra/n8n/kunde')
    sftp = client.open_sftp()
    for fname in os.listdir(N8N_KUNDE_LOCAL):
        if fname.endswith('.json'):
            sftp.put(os.path.join(N8N_KUNDE_LOCAL, fname), f'{REMOTE_APP}/infra/n8n/kunde/{fname}')
            print(f'Upload: infra/n8n/kunde/{fname}')
    sftp.close()

PROVISION_SCRIPT = os.path.join(os.path.dirname(__file__), 'scripts', 'provision_kunde_n8n.py')
BACKUP_SCRIPT = os.path.join(os.path.dirname(__file__), 'scripts', 'backup_agency.sh')
OFFSITE_SCRIPT = os.path.join(os.path.dirname(__file__), 'scripts', 'backup_offsite.sh')
if os.path.isfile(PROVISION_SCRIPT):
    run(client, f'mkdir -p {REMOTE_APP}/scripts')
    sftp = client.open_sftp()
    sftp.put(PROVISION_SCRIPT, f'{REMOTE_APP}/scripts/provision_kunde_n8n.py')
    sftp.close()
    print('Upload: scripts/provision_kunde_n8n.py')

if os.path.isfile(BACKUP_SCRIPT):
    from deploy_shell import upload_shell_script, verify_remote_shell
    run(client, f'mkdir -p {REMOTE_APP}/scripts')
    sftp = client.open_sftp()
    upload_shell_script(sftp, BACKUP_SCRIPT, f'{REMOTE_APP}/scripts/backup_agency.sh')
    sftp.close()
    run(client, 'chmod +x /root/app/scripts/backup_agency.sh')
    ok, msg = verify_remote_shell(client, '/root/app/scripts/backup_agency.sh')
    if not ok:
        print('WARN backup_agency.sh:', msg)
    else:
        print('Upload: scripts/backup_agency.sh (LF ok)')

if os.path.isfile(OFFSITE_SCRIPT):
    from deploy_shell import upload_shell_script, verify_remote_shell
    run(client, f'mkdir -p {REMOTE_APP}/scripts')
    sftp = client.open_sftp()
    upload_shell_script(sftp, OFFSITE_SCRIPT, f'{REMOTE_APP}/scripts/backup_offsite.sh')
    sftp.close()
    run(client, 'chmod +x /root/app/scripts/backup_offsite.sh')
    ok, msg = verify_remote_shell(client, '/root/app/scripts/backup_offsite.sh')
    if not ok:
        print('WARN backup_offsite.sh:', msg)
    else:
        print('Upload: scripts/backup_offsite.sh (LF ok)')

CROSS_BACKUP = os.path.join(os.path.dirname(__file__), 'scripts', 'backup_cross_peers.sh')
DAILY_REPORT_SH = os.path.join(os.path.dirname(__file__), 'scripts', 'nils_daily_report.sh')
COST_SENTRY_SH = os.path.join(os.path.dirname(__file__), 'scripts', 'nils_cost_sentry.sh')
DAILY_REPORT_CLI = os.path.join(os.path.dirname(__file__), 'scripts', 'nils_daily_report_cli.py')
NIGHT_WORKER_SH = os.path.join(os.path.dirname(__file__), 'scripts', 'nils_night_worker.sh')
NIGHT_WORKER_CLI = os.path.join(os.path.dirname(__file__), 'scripts', 'nils_night_worker_cli.py')
if os.path.isfile(CROSS_BACKUP):
    from deploy_shell import upload_shell_script, verify_remote_shell
    run(client, f'mkdir -p {REMOTE_APP}/scripts')
    sftp = client.open_sftp()
    upload_shell_script(sftp, CROSS_BACKUP, f'{REMOTE_APP}/scripts/backup_cross_peers.sh')
    sftp.close()
    run(client, 'chmod +x /root/app/scripts/backup_cross_peers.sh')
    ok, msg = verify_remote_shell(client, '/root/app/scripts/backup_cross_peers.sh')
    if not ok:
        print('WARN backup_cross_peers.sh:', msg)
    else:
        print('Upload: scripts/backup_cross_peers.sh (LF ok)')

# Nils Tagesreport + Kosten-Wächter
if os.path.isfile(DAILY_REPORT_SH):
    from deploy_shell import upload_shell_script, verify_remote_shell
    run(client, f'mkdir -p {REMOTE_APP}/scripts /var/lib/webschmiede')
    sftp = client.open_sftp()
    upload_shell_script(sftp, DAILY_REPORT_SH, f'{REMOTE_APP}/scripts/nils_daily_report.sh')
    if os.path.isfile(COST_SENTRY_SH):
        upload_shell_script(sftp, COST_SENTRY_SH, f'{REMOTE_APP}/scripts/nils_cost_sentry.sh')
    if os.path.isfile(DAILY_REPORT_CLI):
        sftp.put(DAILY_REPORT_CLI, f'{REMOTE_APP}/scripts/nils_daily_report_cli.py')
    if os.path.isfile(NIGHT_WORKER_SH):
        upload_shell_script(sftp, NIGHT_WORKER_SH, f'{REMOTE_APP}/scripts/nils_night_worker.sh')
    if os.path.isfile(NIGHT_WORKER_CLI):
        sftp.put(NIGHT_WORKER_CLI, f'{REMOTE_APP}/scripts/nils_night_worker_cli.py')
    sftp.close()
    run(client, 'chmod +x /root/app/scripts/nils_daily_report.sh /root/app/scripts/nils_cost_sentry.sh /root/app/scripts/nils_night_worker.sh 2>/dev/null || true')
    ok, msg = verify_remote_shell(client, '/root/app/scripts/nils_daily_report.sh')
    if not ok:
        print('WARN nils_daily_report.sh:', msg)
    else:
        print('Upload: scripts/nils_daily_report.sh (LF ok)')
    # Cron: Tagesreport 05:30 UTC, Cost 04:15, Hirn alle 20 Min, Nacht-Digest 20:00 UTC (~22:00 Berlin Sommer)
    run(
        client,
        "("
        "crontab -l 2>/dev/null | grep -v nils_daily_report | grep -v nils_cost_sentry | grep -v nils_night_worker || true; "
        "echo '30 5 * * * /bin/bash /root/app/scripts/nils_daily_report.sh'; "
        "echo '15 4 * * * /bin/bash /root/app/scripts/nils_cost_sentry.sh'; "
        "echo '*/20 * * * * /bin/bash /root/app/scripts/nils_night_worker.sh'; "
        "echo '0 20 * * * /bin/bash /root/app/scripts/nils_night_worker.sh --night'"
        ") | crontab -"
    )
    run(client, 'crontab -l | grep nils_ || true')
    # Sofort einmal Kosten-Wächter (Akquise pausieren falls aktiv)
    run(client, '/bin/bash /root/app/scripts/nils_cost_sentry.sh || true', timeout=60)

# Statische Dateien in Webroot kopieren
print('\nKopiere statische Dateien in Webroot...')
run(client, f'cp {REMOTE_APP}/static/order.html {WEBROOT}/order.html')
run(client, f'cp {REMOTE_APP}/static/admin.html {WEBROOT}/admin.html')
run(client, f'cp {REMOTE_APP}/static/seminare.html {WEBROOT}/seminare.html')
run(client, f'cp {REMOTE_APP}/static/agency.html {WEBROOT}/agency.html')
run(client, f'cp {REMOTE_APP}/static/agency-auth.js {WEBROOT}/agency-auth.js')
run(client, 'mkdir -p /root/app/data /var/www/digitalehandwerkskunst')
run(client, 'cp /root/app/static/agency.html /var/www/digitalehandwerkskunst/agency.html 2>/dev/null || true')
run(client, 'cp /root/app/static/agency-auth.js /var/www/digitalehandwerkskunst/agency-auth.js 2>/dev/null || true')
run(client, f'cp {REMOTE_APP}/static/angebote.html {WEBROOT}/angebote.html')
run(client, f'cp {REMOTE_APP}/static/angebote.json {WEBROOT}/angebote.json')
run(client, f'cp {REMOTE_APP}/static/agency-hub.html {WEBROOT}/agency-hub.html')
run(client, f'cp {REMOTE_APP}/static/nils.html {WEBROOT}/nils.html')
run(client, 'cp /root/app/static/nils.html /var/www/digitalehandwerkskunst/nils.html 2>/dev/null || true')
run(client, f'cp {REMOTE_APP}/static/jay.html {WEBROOT}/jay.html')
run(client, 'cp /root/app/static/jay.html /var/www/digitalehandwerkskunst/jay.html 2>/dev/null || true')
run(client, 'mkdir -p /root/app/agency /var/www/digitalehandwerkskunst')
# Jay Retell Meta
_jay_meta = os.path.join(os.path.dirname(__file__), 'agency', 'jay_retell.json')
if os.path.isfile(_jay_meta):
    sftp = client.open_sftp()
    sftp.put(_jay_meta, '/root/app/agency/jay_retell.json')
    sftp.close()
    print('Upload: agency/jay_retell.json')
run(client, f'mkdir -p {WEBROOT}/ci && cp -r {REMOTE_APP}/static/ci/* {WEBROOT}/ci/ 2>/dev/null || true')
# Freigestelltes Agency-Logo auch auf digitalehandwerkskunst.de (Mails, Hub)
run(client, 'mkdir -p /var/www/digitalehandwerkskunst/ci && cp /root/app/static/ci/webschmiede-logo.png /root/app/static/ci/webschmiede-logo-mark.png /var/www/digitalehandwerkskunst/ci/ 2>/dev/null || true')
run(client, 'cp /root/app/static/ci/webschmiede-logo.png /var/www/digitalehandwerkskunst/webschmiede-logo.png 2>/dev/null || true')
run(client, 'cp /root/app/static/ci/webschmiede-logo-mark.png /var/www/digitalehandwerkskunst/webschmiede-logo-mark.png 2>/dev/null || true')
run(client, f'cp {REMOTE_APP}/static/agency-setup.html {WEBROOT}/agency-setup.html')
run(client, f'cp {REMOTE_APP}/static/agency-setup.html {WEBROOT}/agency-keys.html')
run(client, 'cp /root/app/static/agency-setup.html /var/www/digitalehandwerkskunst/agency-setup.html')
run(client, 'cp /root/app/static/agency-setup.html /var/www/digitalehandwerkskunst/agency-keys.html')
run(client, f'cp {REMOTE_APP}/static/onboarding.html {WEBROOT}/onboarding.html')
run(client, f'cp {REMOTE_APP}/static/uebergabe-handbuch.html {WEBROOT}/uebergabe-handbuch.html')
run(client, f'cp {REMOTE_APP}/static/akquise-report.html {WEBROOT}/akquise-report.html')
run(client, f'cp {REMOTE_APP}/static/b2b-portal.html {WEBROOT}/b2b-portal.html')
run(client, 'cp /root/app/static/b2b-portal.html /var/www/digitalehandwerkskunst/b2b-portal.html 2>/dev/null || true')
run(client, f'cp {REMOTE_APP}/static/buchhaltung-onboarding.html {WEBROOT}/buchhaltung-onboarding.html')
run(client, 'cp /root/app/static/buchhaltung-onboarding.html /var/www/digitalehandwerkskunst/buchhaltung-onboarding.html 2>/dev/null || true')
run(client, f'cp {REMOTE_APP}/static/sales-dashboard.html {WEBROOT}/sales-dashboard.html')
run(client, 'cp /root/app/static/sales-dashboard.html /var/www/digitalehandwerkskunst/sales-dashboard.html 2>/dev/null || true')
run(client, f'cp {REMOTE_APP}/static/sales-angebot.html {WEBROOT}/sales-angebot.html')
run(client, 'cp /root/app/static/sales-angebot.html /var/www/digitalehandwerkskunst/sales-angebot.html 2>/dev/null || true')
run(client, f'cp {REMOTE_APP}/static/transport-kalkulator.html {WEBROOT}/transport-kalkulator.html')
run(client, f'cp {REMOTE_APP}/static/transport-kalkulator.webmanifest {WEBROOT}/transport-kalkulator.webmanifest')
run(client, f'cp {REMOTE_APP}/static/transport-kalkulator-sw.js {WEBROOT}/transport-kalkulator-sw.js')
# Agency-Domain: Pilot für Tobias / MbP
run(client, 'cp /root/app/static/transport-kalkulator.html /var/www/digitalehandwerkskunst/transport-kalkulator.html')
run(client, 'cp /root/app/static/transport-kalkulator.webmanifest /var/www/digitalehandwerkskunst/transport-kalkulator.webmanifest')
run(client, 'cp /root/app/static/transport-kalkulator-sw.js /var/www/digitalehandwerkskunst/transport-kalkulator-sw.js')
run(client, 'cp /root/app/static/tourmeter-mark.svg /var/www/digitalehandwerkskunst/tourmeter-mark.svg')
run(client, f'cp {REMOTE_APP}/static/index.html {WEBROOT}/index.html')
run(client, f'cp {REMOTE_APP}/static/manifest.webmanifest {WEBROOT}/manifest.webmanifest')
run(client, f'cp {REMOTE_APP}/static/sw.js {WEBROOT}/sw.js')
run(client, f'cp {REMOTE_APP}/static/order-push-sw.js {WEBROOT}/order-push-sw.js')
run(client, f'mkdir -p {WEBROOT}/brand && cp -r {REMOTE_APP}/static/brand/* {WEBROOT}/brand/ 2>/dev/null || true')
run(client, f'cp {REMOTE_APP}/static/datenschutz.html {WEBROOT}/datenschutz.html')
run(client, f'cp {REMOTE_APP}/static/impressum.html {WEBROOT}/impressum.html')
run(client, f'cp {REMOTE_APP}/static/favicon.png {WEBROOT}/favicon.png')
run(client, f'cp {REMOTE_APP}/static/favicon-192.png {WEBROOT}/favicon-192.png')
run(client, f'cp {REMOTE_APP}/static/apple-touch-icon.png {WEBROOT}/apple-touch-icon.png')

# Backend neu starten
print('\nStarte Backend neu...')
run(client, f'/root/app/venv/bin/pip install -q stripe==11.4.0 pywebpush==2.0.1 2>/dev/null || true')
run(client, 'systemctl restart snack-api')
import time; time.sleep(3)
run(client, 'systemctl is-active snack-api')

# Prüfen
print('\nVerifikation...')
run(client, rf'grep -c "Online/Offline\|online-toggle\|wait-bar\|loadSiteSettings\|view-artikel" {WEBROOT}/admin.html || echo "0"', timeout=10)
run(client, rf'grep -c "loadSiteSettings\|offline-banner\|waitPickup\|wait-badge" {WEBROOT}/order.html || echo "0"', timeout=10)
run(client, 'curl -s http://localhost:8000/api/push/config | head -c 120', timeout=10)

client.close()

print('\nAgency Setup Smoke-Test...')
import subprocess
smoke = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'scripts', 'smoke_agency_setup.py')])
if smoke.returncode != 0:
    print('WARN: smoke_agency_setup.py meldet Fehler (siehe oben)')

smoke_ops = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'scripts', 'smoke_ops.py')])
if smoke_ops.returncode != 0:
    print('WARN: smoke_ops.py meldet Fehler (siehe oben)')

smoke_faq = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'scripts', 'smoke_jarvis_faq.py')])
if smoke_faq.returncode != 0:
    print('WARN: smoke_jarvis_faq.py meldet Fehler (siehe oben)')

smoke_ch = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'scripts', 'smoke_channels.py')])
if smoke_ch.returncode != 0:
    print('WARN: smoke_channels.py meldet Fehler (siehe oben)')

patch_nils = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'scripts', 'patch_nils_nginx.py')])
if patch_nils.returncode != 0:
    print('WARN: patch_nils_nginx.py meldet Fehler (siehe oben)')

print('\nDeploy fertig!')
