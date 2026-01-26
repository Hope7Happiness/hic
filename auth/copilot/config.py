# config.py
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "mycopilot"
TOKEN_FILE = CONFIG_DIR / "github_token.json"

def save_token(data: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(data, indent=2))

def load_token() -> dict:
    if not TOKEN_FILE.exists():
        raise RuntimeError("Not logged in. Run: mycopilot auth login")
    return json.loads(TOKEN_FILE.read_text())