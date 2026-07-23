#!/usr/bin/env python3
"""Testbestellung SHY001 mit aktuellem Menüpreis."""
import json
import os
import sys
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paramiko
from agency_config import ssh_connect

c = paramiko.SSHClient()
ssh_connect(c)
# get d4 price from server
_, o, _ = c.exec_command(
    "cd /root/app/backend && /root/app/venv/bin/python3 -c \""
    "import sqlite3; db=sqlite3.connect('orders.db'); db.row_factory=sqlite3.Row; "
    "r=db.execute('SELECT price FROM menu_overrides WHERE item_id=\\'d4\\'').fetchone(); "
    "print(r['price'] if r and r['price'] is not None else 7.5)\""
)
price = float(o.read().decode().strip() or "7.5")
print("d4 price:", price)

ts = datetime.now().strftime("%H%M%S")
payload = {
    "firstName": "Webschmiede",
    "lastName": "Test",
    "phone": "+4917012345678",
    "email": "info@digitalehandwerkskunst.de",
    "address": "",
    "deliveryType": "abholung",
    "payMethod": "cash",
    "items": [{"id": "d4", "name": "Lahmacun-Rolle", "price": price, "qty": 1, "free": False}],
    "total": price,
    "wunschzeit": "So schnell wie möglich",
    "notes": "TESTBESTELLUNG Go-Live, bitte auf Fertig setzen",
    "orderNumber": f"TEST-GL-{ts}",
    "_hp": "",
}
data = json.dumps(payload).encode()
req = urllib.request.Request(
    "https://yassine.digitalehandwerkskunst.de/api/order",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=15) as r:
    body = r.read().decode()
    print("ORDER OK", body)

# verify in db
_, o, _ = c.exec_command(
    f"sqlite3 /root/app/backend/orders.db \"SELECT order_number,status,total,created_at FROM orders WHERE order_number='{payload['orderNumber']}'\""
)
print("DB:", o.read().decode())
c.close()
