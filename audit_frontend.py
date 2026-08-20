"""
Audit frontend routes and test live API endpoints for Moovy app.
"""
import urllib.request
import json
import re

BASE_URL = "https://moovy-web-ugu9.onrender.com"

# 1. Fetch JS bundle to find routes and pages
print("=== 1. AUDITING FRONTEND BUNDLE ===")
req = urllib.request.urlopen(f"{BASE_URL}/assets/index-CM8HK3e8.js")
bundle_text = req.read().decode('utf-8')
print(f"Bundle size: {len(bundle_text)} bytes")

# Find routes in React Router
routes = re.findall(r'path:"([^"]+)"', bundle_text)
print("Found frontend routes:", set(routes))

# Search for key UI features in bundle
features = {
    "Friendboard / Friends": "friendboard" in bundle_text.lower(),
    "Watchlist": "watchlist" in bundle_text.lower(),
    "Rating buttons": "like" in bundle_text.lower() and "dislike" in bundle_text.lower(),
    "AI Recommendations": "recommend" in bundle_text.lower(),
    "Vibes Selection": "vibe" in bundle_text.lower(),
    "Invite Code / Share": "invite" in bundle_text.lower() or "code" in bundle_text.lower(),
    "Profile Customization": "nickname" in bundle_text.lower(),
}

print("\n=== FRONTEND FEATURE CHECK ===")
for feat, present in features.items():
    print(f"  [{'OK' if present else 'MISSING'}] {feat}")

# 2. Live API Audit
print("\n=== 2. AUDITING LIVE API ENDPOINTS ===")

def post_json(path, data, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        return e.code, body

def get_json(path, token=None):
    url = f"{BASE_URL}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        return e.code, body

# Login
status, login_res = post_json("/api/auth/login", {"email": "test@gmail.com", "password": "test1234"})
print(f"1. Login Status: {status}")
if status != 200:
    print(f"   Error: {login_res}")
    exit(1)

token = login_res["access_token"]
user_id = login_res["user_id"]
print(f"   Logined User ID: {user_id}")

# Profile
status, profile_res = get_json("/api/profile/me", token)
print(f"2. GET /profile/me Status: {status} -> {profile_res}")

# Rating test
search_status, search_res = get_json("/api/movies/search?title=dark", token)
print(f"3. GET /movies/search Status: {search_status} (Found {len(search_res)} movies)")

if search_res:
    movie_id = search_res[0]["movie_id"]
    movie_title = search_res[0]["title"]
    print(f"   Testing rating on movie: '{movie_title}' ({movie_id})")
    
    rate_status, rate_res = post_json("/api/rating/rate", {"movie_id": movie_id, "status": "LIKE"}, token)
    print(f"4. POST /rating/rate (LIKE) Status: {rate_status} -> {rate_res}")
    
    watchlist_status, watchlist_res = post_json("/api/rating/rate", {"movie_id": movie_id, "status": "WATCHLIST"}, token)
    print(f"5. POST /rating/rate (WATCHLIST) Status: {watchlist_status} -> {watchlist_res}")

# Get Watchlist
status, watchlist = get_json("/api/rating/watchlist", token)
print(f"6. GET /rating/watchlist Status: {status} (Items: {len(watchlist) if isinstance(watchlist, list) else watchlist})")

# Create Session
status, session_res = post_json("/api/session/create", {"meeting_type": "SOLO"}, token)
print(f"7. POST /session/create Status: {status} -> {session_res}")

if status == 200:
    session_id = session_res["session_id"]
    invite_code = session_res["invite_code"]
    print(f"   Session ID: {session_id}, Invite Code: {invite_code}")
    
    # Submit preferences (PUT)
    pref_req = urllib.request.Request(f"{BASE_URL}/api/session/{session_id}/preferences",
                                       data=json.dumps({
                                           "preferences": {
                                               "vibes": ["LAUGH_RIOT", "DATE_NIGHT"],
                                               "hard_nos": [],
                                               "max_runtime": 120,
                                               "allow_seen": False,
                                               "eras": [],
                                               "no_anime": False,
                                               "no_animation": False
                                           }
                                       }).encode('utf-8'),
                                       headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                                       method="PUT")
    try:
        with urllib.request.urlopen(pref_req) as resp:
            pref_status, pref_res = resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        pref_status, pref_res = e.code, e.read().decode('utf-8')
    print(f"8. PUT /session/{session_id}/preferences Status: {pref_status} -> {pref_res}")

    # Generate Recommendations
    print("9. Generating AI recommendations...")
    rec_status, rec_res = post_json(f"/api/session/{session_id}/recommend", {}, token)
    print(f"   POST /session/{session_id}/recommend Status: {rec_status}")
    if rec_status == 200:
        print("\n=== AI RECOMMENDATION RESULT ===")
        print(json.dumps(rec_res, indent=2))
    else:
        print(f"   AI Recommendation Error: {rec_res}")
