"""
SNACK HOUSE YASSINE – Automatischer Bondruck
============================================
Läuft im Hintergrund auf Hassans PC.
Fragt alle 10 Sekunden neue Bestellungen ab und druckt automatisch.

Installation:
  pip install requests pywin32 python-escpos
  python autoprint.py

Konfiguration weiter unten anpassen.
"""
import requests, json, time, os, sys
from datetime import datetime

# ── KONFIGURATION ─────────────────────────────────────────────────────────────
API_BASE       = "https://yassine.digitalehandwerkskunst.de/api"
ADMIN_PASSWORD = "snackhouse2026"
POLL_INTERVAL  = 10   # Sekunden

# Druckmodus: "windows" (normaler PC-Drucker) oder "escpos" (Bondrucker USB/Netzwerk)
PRINT_MODE     = "windows"

# Für normalen Windows-Drucker:
PRINTER_NAME   = ""  # Leer = Standard-Drucker. Oder z.B. "EPSON TM-T20"

# Für ESC/POS Netzwerkdrucker:
PRINTER_IP     = ""  # z.B. "192.168.1.100"
PRINTER_PORT   = 9100

# ─────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "Content-Type": "application/json",
    "X-Admin-Password": ADMIN_PASSWORD,
}

printed_orders = set()
STATE_FILE = os.path.join(os.path.dirname(__file__), "printed.json")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return set(json.load(f))
    return set()

def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump(list(printed_orders), f)

def format_bon(order):
    line = "─" * 32
    items = "\n".join(
        f"{i['qty']}x {i['name'][:22]:<22} {i['price']*i['qty']:>6.2f} EUR"
        for i in order.get("items", [])
    )
    del_label = "LIEFERUNG" if order["delivery_type"] == "lieferung" else "ABHOLUNG"
    ps = (order.get("payment_status") or "").lower()
    if order.get("payment_refund_required"):
        pay_label = "ONLINE BEZAHLT - REFUND ERFORDERLICH"
    elif ps == "paid":
        pay_label = "ONLINE BEZAHLT"
    elif order.get("pay_method") == "stripe" and ps == "pending":
        pay_label = "ONLINE-ZAHLUNG AUSSTEHEND"
    else:
        pay_label = {"cash": "BARZAHLUNG", "card": "EC-Karte", "stripe": "Online"}.get(
            order.get("pay_method"), order.get("pay_method") or ""
        )
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    bon = f"""
================================
    SNACK HOUSE YASSINE
Dr.-Felix-Gerhardus-Str. 7
        Mechernich
================================
{del_label}
Nr: {order["order_number"]}
Zeit: {now}
{line}
{order["first_name"]} {order["last_name"]}
{order["phone"]}"""

    if order["delivery_type"] == "lieferung" and order.get("address"):
        bon += f"\n{order['address']}"
    if order.get("wunschzeit"):
        bon += f"\nWunschzeit: {order['wunschzeit']}"

    bon += f"""
{line}
{items}
{line}
GESAMT: {order["total"]:.2f} EUR
Zahlung: {pay_label}"""

    if order.get("notes") and order["notes"] not in ("-", ""):
        bon += f"\n{line}\nHinweis: {order['notes']}"

    bon += f"""
{line}
    Danke fuer Ihren Besuch!
================================
"""
    return bon

def print_windows(bon_text, order_number):
    try:
        import win32print, win32ui
        from PIL import Image, ImageDraw, ImageFont
        import io

        printer = PRINTER_NAME or win32print.GetDefaultPrinter()
        hprinter = win32print.OpenPrinter(printer)
        try:
            hjob = win32print.StartDocPrinter(hprinter, 1, (f"Bestellung {order_number}", None, "RAW"))
            win32print.StartPagePrinter(hprinter)
            win32print.WritePrinter(hprinter, bon_text.encode("cp1252", errors="replace"))
            win32print.EndPagePrinter(hprinter)
            win32print.EndDocPrinter(hprinter)
        finally:
            win32print.ClosePrinter(hprinter)
        print(f"  [OK] Gedruckt auf: {printer}")
    except Exception as e:
        print(f"  [FEHLER] Windows-Druck: {e}")
        # Fallback: txt-Datei speichern
        fname = os.path.join(os.path.dirname(__file__), f"bon_{order_number}.txt")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(bon_text)
        print(f"  [FALLBACK] Gespeichert als: {fname}")

def print_escpos(bon_text):
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((PRINTER_IP, PRINTER_PORT))
            # ESC/POS: Initialize, center, bold on
            s.sendall(b"\x1b\x40")           # ESC @ Initialize
            s.sendall(bon_text.encode("cp437", errors="replace"))
            s.sendall(b"\n\n\n\n")           # Feed + cut
            s.sendall(b"\x1d\x56\x00")       # GS V 0 = Full cut
        print(f"  [OK] ESC/POS Druck an {PRINTER_IP}:{PRINTER_PORT}")
    except Exception as e:
        print(f"  [FEHLER] ESC/POS: {e}")

def print_order(order):
    bon = format_bon(order)
    print(f"\n{'='*40}")
    print(f"NEUE BESTELLUNG: {order['order_number']}")
    print(bon)
    if PRINT_MODE == "escpos" and PRINTER_IP:
        print_escpos(bon)
    else:
        print_windows(bon, order["order_number"])

def poll():
    global printed_orders
    try:
        r = requests.get(f"{API_BASE}/admin/orders", headers=HEADERS, timeout=10)
        if not r.ok:
            return
        orders = r.json()
        new_orders = [o for o in orders if o["status"] == "neu" and o["order_number"] not in printed_orders]
        for o in new_orders:
            print_order(o)
            printed_orders.add(o["order_number"])
        if new_orders:
            save_state()
    except Exception as e:
        print(f"  [POLL FEHLER] {e}")

def main():
    global printed_orders
    printed_orders = load_state()
    print("=" * 40)
    print("SNACK HOUSE – Auto-Drucker gestartet")
    print(f"Server:   {API_BASE}")
    print(f"Drucker:  {PRINT_MODE.upper()}")
    print(f"Intervall:{POLL_INTERVAL}s")
    print("=" * 40)
    print("Warte auf neue Bestellungen...\n")
    while True:
        poll()
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
