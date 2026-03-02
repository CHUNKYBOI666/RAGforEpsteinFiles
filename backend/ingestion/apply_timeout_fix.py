"""Apply fix_chunk_search_timeout.sql via SUPABASE_DB_URL. Run from backend/: python ingestion/apply_timeout_fix.py"""
from pathlib import Path
import importlib.util
import sys

_backend_dir = Path(__file__).resolve().parent.parent
if (_backend_dir / ".env").exists():
    from dotenv import load_dotenv
    load_dotenv(_backend_dir / ".env", override=True)
_spec = importlib.util.spec_from_file_location("config", _backend_dir / "config.py")
config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(config)
url = getattr(config, "SUPABASE_DB_URL", "")
if not url:
    print("SUPABASE_DB_URL not set in .env")
    sys.exit(1)

import psycopg
sql_file = Path(__file__).resolve().parent / "fix_chunk_search_timeout.sql"
statements = []
for line in sql_file.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("--"):
        continue
    statements.append(line)

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        for stmt in statements:
            try:
                cur.execute(stmt)
                print("OK:", stmt[:70] + "..." if len(stmt) > 70 else stmt)
            except Exception as e:
                print("Skip:", e)
print("Done.")
