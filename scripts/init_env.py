"""Generate local-only Compose secrets without printing them."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    raise SystemExit(".env already exists; keeping it unchanged")
target.write_text(
    "APP_SECRET=" + secrets.token_urlsafe(48) + "\n"
    "DB_PASSWORD=" + secrets.token_hex(24) + "\n"
    "SUPPORTFLOW_DEMO=1\nCOOKIE_SECURE=0\n"
    "APP_ORIGIN=http://localhost:5080\nAI_PROVIDER=demo\n", encoding="utf-8")
print("Created local .env with random secrets. Do not commit it.")
