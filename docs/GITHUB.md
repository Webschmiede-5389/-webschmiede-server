# GitHub einrichten — Webschmiede Server

## 1. Secrets lokal (einmalig)

```powershell
copy deploy.secrets.local.example deploy.secrets.local
# SERVER_PASSWORD eintragen
```

`deploy.secrets.local` wird **nicht** committed.

## 2. Repo auf GitHub anlegen

1. https://github.com/new  
2. Name: `webschmiede-server` (oder `jarvis-server`)  
3. **Private** Repository  
4. Kein README/License von GitHub hinzufügen (wir haben schon Code)

## 3. Ersten Push

```powershell
cd C:\Users\kumex\OneDrive\Desktop\Jarvis\Server
git init
git add .
git commit -m "Initial commit: Webschmiede agency stack (Snack House SHY001)"
git branch -M main
git remote add origin https://github.com/DEIN-USERNAME/webschmiede-server.git
git push -u origin main
```

## 4. Cursor Cloud verbinden

1. Cursor → Settings → GitHub verbinden  
2. [cursor.com/agents](https://cursor.com/agents) → Repository wählen  
3. Cloud Agent kann dann nachts/unterwegs am Code arbeiten

## Was NICHT ins Repo gehört

| Datei | Grund |
|-------|--------|
| `deploy.secrets.local` | SSH-Passwort |
| `n8n-credentials.local.txt` | n8n-Login |
| `app/backend/.env` | API-Keys, Admin-Passwort |

## Deploy nach Push

Lokal weiterhin:

```powershell
python deploy.py
```

Server-Secrets bleiben in `/root/app/backend/.env` auf Hetzner.
