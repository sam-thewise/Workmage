"""Quick test of twitter-automation HTTP and MCP endpoints."""
import json
import os
import sys

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

BASE = "http://127.0.0.1:8010"
TIMEOUT = 15.0

def main():
    print("1. GET /health ...")
    try:
        r = httpx.get(f"{BASE}/health", timeout=TIMEOUT)
        print(f"   Status: {r.status_code} -> {r.json()}")
    except Exception as e:
        print(f"   FAIL: {e}")
        return 1

    print("\n2. POST /mcp/twitter tools/list ...")
    try:
        r = httpx.post(
            f"{BASE}/mcp/twitter",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            timeout=TIMEOUT,
        )
        print(f"   Status: {r.status_code}")
        data = r.json()
        tools = data.get("result", {}).get("tools", [])
        print(f"   Tools: {[t['name'] for t in tools]}")
    except Exception as e:
        print(f"   FAIL: {e}")
        return 1

    print("\n3. POST /mcp/twitter tools/call check_x_sessions ...")
    try:
        r = httpx.post(
            f"{BASE}/mcp/twitter",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "check_x_sessions", "arguments": {}},
            },
            timeout=TIMEOUT,
        )
        print(f"   Status: {r.status_code}")
        data = r.json()
        content = data.get("result", {}).get("content", [{}])[0].get("text", "{}")
        print(f"   Result: {json.dumps(json.loads(content), indent=2)}")
    except Exception as e:
        print(f"   FAIL: {e}")
        return 1

    print("\n4. POST /mcp/twitter tools/call fetch_x_profile_timeline (handle=twitterdev, limit=5) ...")
    try:
        r = httpx.post(
            f"{BASE}/mcp/twitter",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "fetch_x_profile_timeline",
                    "arguments": {"handle": "twitterdev", "limit": 5},
                },
            },
            timeout=TIMEOUT,
        )
        print(f"   Status: {r.status_code}")
        data = r.json()
        content = data.get("result", {}).get("content", [{}])[0].get("text", "{}")
        out = json.loads(content)
        if "error" in out:
            print(f"   Error: {out['error']}")
        else:
            print(f"   source={out.get('source')} handle={out.get('handle')} count={out.get('count')}")
            for p in out.get("posts", [])[:3]:
                text = (p.get("text") or "")[:55]
                print(f"   - {p.get('id')} {p.get('author_handle','')}: {text}...")
    except Exception as e:
        print(f"   FAIL: {e}")
        return 1

    print("\n5. POST /mcp/twitter tools/call fetch_x_post (single tweet by id) ...")
    try:
        r = httpx.post(
            f"{BASE}/mcp/twitter",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "fetch_x_post",
                    "arguments": {"url_or_id": "20"},  # Twitter's first tweet
                },
            },
            timeout=TIMEOUT,
        )
        print(f"   Status: {r.status_code}")
        data = r.json()
        content = data.get("result", {}).get("content", [{}])[0].get("text", "{}")
        out = json.loads(content)
        if "error" in out:
            print(f"   Error: {out['error']}")
        else:
            post = out.get("post", {})
            print(f"   source={out.get('source')} post id={post.get('id')} @{post.get('author_handle','')}")
            print(f"   text: {post.get('text', '')[:80]}...")
    except Exception as e:
        print(f"   FAIL: {e}")
        return 1

    print("\nAll checks passed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
