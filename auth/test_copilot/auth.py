# auth.py
import time
import requests
import urllib3
from config import save_token

CLIENT_ID = "YOUR_ID"  # The ID you get from the OAuth App

# Disable SSL warnings for LibreSSL compatibility
try:
    urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)
except AttributeError:
    # urllib3 < 2.0 doesn't have NotOpenSSLWarning
    pass


def auth_login():
    # Step 1: request device code
    # Use a session with retry and timeout settings
    session = requests.Session()
    r = session.post(
        "https://github.com/login/device/code",
        headers={"Accept": "application/json"},
        data={
            "client_id": CLIENT_ID,
            "scope": "read:user user:email"
        },
        timeout=30,
        verify=True,
    )
    r.raise_for_status()
    data = r.json()

    print(f"\n👉 Open this URL:\n{data['verification_uri']}")
    print(f"👉 Enter code: {data['user_code']}\n")

    # Step 2: poll token
    while True:
        time.sleep(data["interval"])
        r = session.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": CLIENT_ID,
                "device_code": data["device_code"],
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            timeout=30,
            verify=True,
        )
        token = r.json()
        if "access_token" in token:
            save_token(token)
            print("✅ Logged in successfully")
            return
        if token.get("error") != "authorization_pending":
            raise RuntimeError(token)