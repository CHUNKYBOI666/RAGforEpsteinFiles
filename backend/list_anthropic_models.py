"""Print Anthropic model IDs available to your API key. Run from backend/: python list_anthropic_models.py"""
from pathlib import Path
import os
import sys

_backend = Path(__file__).resolve().parent
sys.path.insert(0, str(_backend))
from dotenv import load_dotenv
load_dotenv(_backend / ".env", override=True)

from anthropic import Anthropic

key = os.getenv("ANTHROPIC_API_KEY")
if not key:
    print("ANTHROPIC_API_KEY not set in .env")
    sys.exit(1)

client = Anthropic(api_key=key)
page = client.models.list()
print("Model IDs available for your key (use one as ANTHROPIC_MODEL in .env):")
for m in page.data:
    print(f"  {m.id}")
