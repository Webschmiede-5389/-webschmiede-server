# Snack House – Auto-Drucker Setup

## Option A: Drucken-Button im Dashboard (kein Setup)
→ Im Admin-Dashboard auf den blauen "Drucken"-Button klicken.
→ Normaler Windows-Druckdialog öffnet sich.
→ Funktioniert sofort mit jedem Drucker.

---

## Option B: Automatischer Druck (Skript auf Hassans PC)

### Schritt 1: Python installieren
→ https://python.org/downloads → "Install Now" klicken

### Schritt 2: Abhängigkeiten installieren
```
pip install requests pywin32
```

### Schritt 3: Drucker konfigurieren
→ `autoprint.py` öffnen
→ Zeile `PRINTER_NAME = ""` → Druckernamen eintragen
→ (Druckernamen findest du unter: Windows → Einstellungen → Drucker)

### Schritt 4: Starten
```
python autoprint.py
```

### Schritt 5: Autostart einrichten (optional)
Damit das Skript automatisch beim PC-Start läuft:
→ Win + R → `shell:startup`
→ Shortcut zu `autoprint.py` dort ablegen

---

## Option C: Netzwerk-Bondrucker (WLAN/LAN, vollautomatisch)

### Empfohlene Drucker:
| Modell | Preis | Anschluss |
|---|---|---|
| Epson TM-T20III | ~150€ | USB + Ethernet |
| Star TSP143IIILAN | ~180€ | Ethernet/WLAN |
| Epson TM-T88VII | ~250€ | USB + Ethernet + WLAN |

### Setup:
1. Drucker per LAN/WLAN mit Router verbinden
2. IP-Adresse des Druckers herausfinden (meist 192.168.1.xxx)
3. In `autoprint.py`:
   ```
   PRINT_MODE  = "escpos"
   PRINTER_IP  = "192.168.1.100"  ← echte IP eintragen
   PRINTER_PORT= 9100
   ```
4. Skript starten → druckt automatisch ohne PC-Interaktion

### Vorteil:
→ Drucker kann in der Küche stehen
→ Kein PC muss am Drucker hängen
→ Vollautomatisch, keine Klicks nötig
