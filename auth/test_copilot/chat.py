# chat.py
import requests
from config import load_token

COPILOT_CHAT_ENDPOINT = "https://api.githubcopilot.com/chat/completions"

def chat(prompt: str, model: str):
    token = load_token()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Copilot-Integration-Id": "vscode-chat",
        "User-Agent": "VSCode/1.86.0 (Copilot)",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "stream": False,
    }

    r = requests.post(COPILOT_CHAT_ENDPOINT, headers=headers, json=payload, timeout=60)

    if r.status_code >= 400:
        raise RuntimeError(
            f"Copilot chat failed: {r.status_code}\n"
            f"Response headers: {dict(r.headers)}\n"
            f"Response body: {r.text}\n"
            f"Request payload: {payload}\n"
        )

    data = r.json()
    return data["choices"][0]["message"]["content"]