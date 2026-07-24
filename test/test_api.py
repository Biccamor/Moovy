"""
Szybka testerka movieNight API.
Uruchomienie: python test_api.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')  # fix Windows CP1250
import requests
import json
import uuid

BASE = "http://localhost:8010"

# ── konfiguracja ────────────────────────────────────────────────────────────
EMAIL    = "testowy@example.com"
PASSWORD = "testpass123"
# ────────────────────────────────────────────────────────────────────────────

s = requests.Session()
s.headers.update({"Content-Type": "application/json"})


def pprint(label: str, data):
    print(f"\n{'='*55}")
    print(f"  {label}")
    print('='*55)
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def register():
    r = s.post(f"{BASE}/auth/register", json={
        "email": EMAIL, "password": PASSWORD, "confirm_password": PASSWORD
    })
    if r.status_code == 200:
        pprint("Zarejestrowano", r.json())
    elif r.status_code == 400:
        print(f"\n  Konto już istnieje ({EMAIL}), loguję...")
    else:
        r.raise_for_status()


def login() -> tuple[str, str, str]:
    r = s.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    data = r.json()
    pprint("Zalogowano", {k: (v[:40]+"...") if "token" in k else v for k, v in data.items()})
    return data["access_token"], data["refresh_token"], str(data["user_id"])


def create_session(token: str, user_id: str) -> str:
    s.headers.update({"Authorization": f"Bearer {token}"})
    body = {
        "host_id": user_id,
        "invite_code": "TEST1",
        "meeting_type": "EKIPA",
        "users": [
            {
                "user_id": user_id,
                "user_name": "Tester",
                "personal_vibe": {
                    "vibes": ["ADRENALINE", "SPINE_CHILLING"],
                    "hard_nos": [],
                    "max_runtime": 150,
                    "allow_seen": False,
                    "eras": []
                }
            },
            {
                "user_id": str(uuid.uuid4()),
                "user_name": "Alice",
                "personal_vibe": {
                    "vibes": ["EXISTENTIAL", "SPINE_CHILLING"],
                    "hard_nos": [],
                    "max_runtime": 120,
                    "allow_seen": True,
                    "eras": []
                }
            },
            {
                "user_id": str(uuid.uuid4()),
                "user_name": "Bob",
                "personal_vibe": {
                    "vibes": ["MIND_BENDER", "EXISTENTIAL"],
                    "hard_nos": [],
                    "max_runtime": 180,
                    "allow_seen": False,
                    "eras": []
                }
            }
        ]
    }
    r = s.post(f"{BASE}/recommendation/session", json=body)
    r.raise_for_status()
    data = r.json()
    pprint("Sesja utworzona", data)
    return data["session_id"]


def get_recommendation(token: str, session_id: str):
    s.headers.update({"Authorization": f"Bearer {token}"})
    print(f"\n  Odpytuję rekomendacje (może chwilę trwać — LLM + reranker)...")
    r = s.post(f"{BASE}/recommendation/{session_id}")
    r.raise_for_status()
    data = r.json()
    pprint("Rekomendacja", data)

    # szybki check czy poster i data wróciły
    poster = data.get("poster_path", "")
    release = data.get("release_date")
    print(f"\n  poster_path  : {'ok ' + poster if poster else 'brak'}")
    print(f"  release_date : {'ok ' + str(release) if release else 'brak'}")


def refresh_test(refresh_token: str):
    r = s.post(f"{BASE}/auth/refresh", json={"refresh_token": refresh_token})
    r.raise_for_status()
    pprint("Refresh tokena", {k: v[:30] + "..." for k, v in r.json().items() if "token" in k})


if __name__ == "__main__":
    print("=== movieNight API testerka ===")
    register()
    token, refresh_token, user_id = login()

    refresh_test(refresh_token)

    session_id = create_session(token, user_id)
    get_recommendation(token, session_id)
