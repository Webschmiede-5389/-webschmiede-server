# Branding Modes

Siehe auch `config/branding.example.yaml` und `app/backend/brand_config.py`.

| Mode | Shell-Logo | Farben |
|------|------------|--------|
| AGENCY_INTERNAL | WebSchmiede | Tokens kanonisch |
| AGENCY_CUSTOMER_MANAGEMENT | WebSchmiede (+ optional Kunden-Chip) | Agency |
| CUSTOMER_PORTAL | Tenant | validierte Hex-Tokens |
| PUBLIC_CUSTOMER_SITE | Tenant | frei im Rahmen kunden.json brand |
| EXTERNAL_SERVICE_CARD | Agency ToolCard | Vendor UI unverändert |

Freies CSS/JS von Kunden: **verboten** (`BrandConfigError`).
