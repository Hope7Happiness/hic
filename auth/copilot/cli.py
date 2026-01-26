# cli.py
import sys
from auth import auth_login
from chat import chat

from models import list_models


def main():
    if sys.argv[1:] == ["models"]:
        for m in list_models():
            print(m)
        return
    if sys.argv[1:] == ["auth", "login"]:
        auth_login()
        return

    if sys.argv[1] == "run":
        prompt = sys.argv[2]
        model = sys.argv[3] if len(sys.argv) > 3 else "claude-sonnet-4.5"
        print(chat(prompt, model))
        return

    print("""
Usage:
  mycopilot auth login
  mycopilot run "Hello" [model]
""")

if __name__ == "__main__":
    main()