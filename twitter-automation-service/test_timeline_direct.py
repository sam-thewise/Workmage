"""Call Twitter API v2 user timeline directly to see full error response."""
import json
import os

# Load .env from repo root
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.isfile(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"')

import httpx

token = os.getenv("TWITTER_BEARER_TOKEN") or os.getenv("TWITTER_AUTOMATION_BEARER_TOKEN")
if not token:
    print("No bearer token in env")
    exit(1)

# Get user id for "twitter"
r = httpx.get(
    "https://api.twitter.com/2/users/by/username/twitter",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    timeout=10.0,
)
print("users/by/username/twitter:", r.status_code, r.json())
if r.status_code != 200:
    exit(1)
user_id = r.json()["data"]["id"]

# User timeline with same params as app
params = {
    "max_results": 5,
    "exclude": "replies,retweets",
    "tweet.fields": "created_at,text,author_id",
    "expansions": "author_id",
    "user.fields": "username",
}
r2 = httpx.get(
    f"https://api.twitter.com/2/users/{user_id}/tweets",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    params=params,
    timeout=10.0,
)
print("\nusers/{id}/tweets:", r2.status_code)
print(json.dumps(r2.json(), indent=2))
