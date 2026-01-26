# models.py
import requests
from config import load_token

MODELS_ENDPOINT = "https://api.githubcopilot.com/models"

def list_models():
    token = load_token()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Copilot-Integration-Id": "vscode-chat",
        "User-Agent": "VSCode/1.86.0 (Copilot)",
    }
    r = requests.get(MODELS_ENDPOINT, headers=headers, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"models failed: {r.status_code}\n{r.text}")
    data = r.json()
    # 兼容两种可能结构
    if isinstance(data, dict) and "data" in data:
        return [m.get("id") for m in data["data"] if "id" in m]
    if isinstance(data, list):
        return [m.get("id") for m in data if "id" in m]
    return []