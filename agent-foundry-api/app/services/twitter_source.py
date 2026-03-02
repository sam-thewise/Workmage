"""Backend-only Twitter/X source service using session cookies."""
from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5H5tB5M6Nw6N2c"
    "%3D1Zv7ttfk8AN2es0wA4JfN0R7vS6T85Z4vU9P2v2H6A"
)

AUTH_FAILURE_STATUSES = {401, 403, 429}
TRANSIENT_FAILURE_STATUSES = {408, 425, 429, 500, 502, 503, 504}


class TwitterSourceError(Exception):
    """Base error raised by the Twitter source service."""


class TwitterConfigurationError(TwitterSourceError):
    """Raised when source configuration is invalid."""


class TwitterUpstreamError(TwitterSourceError):
    """Raised when Twitter/X upstream request fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(slots=True)
class XSession:
    """Session credentials loaded from JSONL."""

    auth_token: str
    ct0: str
    username: str | None = None
    account_id: str | None = None

    @classmethod
    def from_jsonl_line(cls, line: str) -> XSession | None:
        raw = (line or "").strip()
        if not raw:
            return None
        data = json.loads(raw)
        if data.get("kind") != "cookie":
            return None
        auth_token = (data.get("auth_token") or "").strip()
        ct0 = (data.get("ct0") or "").strip()
        if not auth_token or not ct0:
            return None
        return cls(
            auth_token=auth_token,
            ct0=ct0,
            username=(data.get("username") or "").strip() or None,
            account_id=(data.get("id") or "").strip() or None,
        )

    def label(self) -> str:
        if self.username:
            return self.username
        if self.account_id:
            return f"id:{self.account_id}"
        return "unknown"


@dataclass(slots=True)
class SessionState:
    """Mutable state for one loaded session."""

    session: XSession
    failures: int = 0
    cooldown_until: float = 0.0


@dataclass(slots=True)
class SessionPool:
    """Session rotation with cooldown and global breaker."""

    states: list[SessionState] = field(default_factory=list)
    cooldown_sec: int = 60
    breaker_threshold: int = 6
    breaker_reset_sec: int = 180
    _global_auth_failures: int = 0
    _breaker_until: float = 0.0

    def acquire(self) -> tuple[int, XSession]:
        now = time.monotonic()
        if self._breaker_until > now:
            raise TwitterUpstreamError(
                "Twitter source circuit breaker is open; retry shortly.",
                status_code=503,
            )
        available: list[tuple[int, SessionState]] = []
        for idx, state in enumerate(self.states):
            if state.cooldown_until <= now:
                available.append((idx, state))
        if not available:
            raise TwitterUpstreamError(
                "No active Twitter sessions available (all in cooldown).",
                status_code=503,
            )
        available.sort(key=lambda item: item[1].failures)
        pick_idx, pick_state = available[0]
        return pick_idx, pick_state.session

    def report_success(self, idx: int) -> None:
        state = self.states[idx]
        state.failures = 0
        state.cooldown_until = 0.0
        self._global_auth_failures = 0

    def report_failure(self, idx: int, status_code: int | None) -> None:
        state = self.states[idx]
        state.failures += 1
        cooldown = min(600, self.cooldown_sec * max(1, state.failures))
        jitter = random.randint(0, max(1, cooldown // 4))
        state.cooldown_until = time.monotonic() + cooldown + jitter
        if status_code in AUTH_FAILURE_STATUSES:
            self._global_auth_failures += 1
            if self._global_auth_failures >= self.breaker_threshold:
                self._breaker_until = time.monotonic() + self.breaker_reset_sec
                self._global_auth_failures = 0
                logger.warning("Twitter source breaker opened for %ss", self.breaker_reset_sec)


class TwitterSourceService:
    """Fetch and normalize Twitter/X content for internal analysis pipelines."""

    def __init__(self) -> None:
        self.enabled = bool(settings.X_SOURCE_ENABLED)
        self.base_url = settings.X_API_BASE.rstrip("/")
        self.bearer_token = settings.X_BEARER_TOKEN or DEFAULT_BEARER_TOKEN
        self.timeout_sec = max(3, int(settings.X_REQUEST_TIMEOUT_SEC))
        self.max_retries = max(1, int(settings.X_MAX_RETRIES))
        self.backoff_base_ms = max(50, int(settings.X_BACKOFF_BASE_MS))
        self.user_agent = settings.X_USER_AGENT
        self.proxy_url = settings.X_PROXY_URL.strip() or None
        self.query_user_by_screen_name = settings.X_QUERY_USER_BY_SCREEN_NAME.strip()
        self.query_user_tweets = settings.X_QUERY_USER_TWEETS.strip()
        self.query_tweet_detail = settings.X_QUERY_TWEET_DETAIL.strip()
        self.query_search = settings.X_QUERY_SEARCH_TIMELINE.strip()
        self.features_json = settings.X_API_FEATURES_JSON.strip()
        self._pool = SessionPool(
            states=[SessionState(session=s) for s in self._load_sessions()],
            cooldown_sec=max(1, int(settings.X_SESSION_COOLDOWN_SEC)),
            breaker_threshold=max(1, int(settings.X_BREAKER_FAILURE_THRESHOLD)),
            breaker_reset_sec=max(5, int(settings.X_BREAKER_RESET_SEC)),
        )

    def _load_sessions(self) -> list[XSession]:
        path = Path(settings.X_SESSIONS_FILE).expanduser()
        if not path.exists():
            if self.enabled:
                raise TwitterConfigurationError(f"X sessions file not found: {path}")
            logger.info("Twitter source disabled and sessions file missing: %s", path)
            return []
        sessions: list[XSession] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                parsed = XSession.from_jsonl_line(line)
            except Exception:
                parsed = None
            if parsed:
                sessions.append(parsed)
        if self.enabled and not sessions:
            raise TwitterConfigurationError("X sessions file exists but contains no valid cookie sessions.")
        return sessions

    def startup_validate(self) -> None:
        if not self.enabled:
            logger.info("Twitter source is disabled (X_SOURCE_ENABLED=false).")
            return
        logger.info("Twitter source enabled with %s loaded session(s).", len(self._pool.states))

    def _headers_for(self, session: XSession) -> dict[str, str]:
        cookie = f"auth_token={session.auth_token}; ct0={session.ct0};"
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "x-csrf-token": session.ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": "en",
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Cookie": cookie,
        }

    def _graphql_get(
        self,
        operation_name: str,
        query_id: str,
        variables: dict[str, Any],
        features: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not query_id:
            raise TwitterConfigurationError(f"Missing query id for operation {operation_name}")
        params = {
            "variables": json.dumps(variables, separators=(",", ":")),
        }
        if features is None:
            params["features"] = self.features_json or "{}"
        else:
            params["features"] = json.dumps(features, separators=(",", ":"))
        target = f"{self.base_url}/i/api/graphql/{query_id}/{operation_name}"

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            idx, session = self._pool.acquire()
            try:
                with httpx.Client(
                    timeout=self.timeout_sec,
                    follow_redirects=True,
                    proxy=self.proxy_url,
                    headers=self._headers_for(session),
                ) as client:
                    response = client.get(target, params=params)
                status = response.status_code
                if status >= 400:
                    msg = f"Twitter API {operation_name} failed with status {status}"
                    raise TwitterUpstreamError(msg, status_code=status)
                payload = response.json()
                self._pool.report_success(idx)
                return payload if isinstance(payload, dict) else {}
            except TwitterUpstreamError as exc:
                self._pool.report_failure(idx, exc.status_code)
                last_error = exc
                logger.warning(
                    "Twitter request failure op=%s status=%s attempt=%s session=%s",
                    operation_name,
                    exc.status_code,
                    attempt,
                    session.label(),
                )
                if exc.status_code not in TRANSIENT_FAILURE_STATUSES and exc.status_code not in AUTH_FAILURE_STATUSES:
                    break
            except Exception as exc:
                self._pool.report_failure(idx, None)
                last_error = exc
                logger.warning(
                    "Twitter request exception op=%s attempt=%s session=%s err=%s",
                    operation_name,
                    attempt,
                    session.label(),
                    type(exc).__name__,
                )
            if attempt < self.max_retries:
                base = self.backoff_base_ms * attempt
                sleep_sec = (base + random.randint(0, base)) / 1000.0
                time.sleep(sleep_sec)
        if isinstance(last_error, TwitterSourceError):
            raise last_error
        raise TwitterUpstreamError(f"Twitter API request failed: {last_error}")

    @staticmethod
    def _extract_tweet_id(url_or_id: str) -> str:
        value = (url_or_id or "").strip()
        if not value:
            raise ValueError("url_or_id is required")
        if value.isdigit():
            return value
        match = re.search(r"/status/(\d+)", value)
        if match:
            return match.group(1)
        raise ValueError("Could not parse tweet id from input")

    @staticmethod
    def _walk(obj: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(obj, dict):
            if obj.get("rest_id") and isinstance(obj.get("legacy"), dict):
                found.append(obj)
            for value in obj.values():
                found.extend(TwitterSourceService._walk(value))
        elif isinstance(obj, list):
            for item in obj:
                found.extend(TwitterSourceService._walk(item))
        return found

    @staticmethod
    def _normalize_tweet(tweet: dict[str, Any]) -> dict[str, Any] | None:
        legacy = tweet.get("legacy") or {}
        if not legacy:
            return None
        core = tweet.get("core") or {}
        user_result = (core.get("user_results") or {}).get("result") or {}
        user_legacy = user_result.get("legacy") or {}
        handle = user_legacy.get("screen_name") or legacy.get("screen_name") or ""
        text = legacy.get("full_text") or ""
        note = (((tweet.get("note_tweet") or {}).get("note_tweet_results") or {}).get("result") or {}).get("text")
        if note:
            text = note
        tweet_id = str(tweet.get("rest_id") or "")
        if not tweet_id:
            return None
        post_url = f"https://x.com/{handle}/status/{tweet_id}" if handle else f"https://x.com/i/web/status/{tweet_id}"
        return {
            "id": tweet_id,
            "author_handle": handle,
            "author_name": user_legacy.get("name") or "",
            "text": text,
            "url": post_url,
            "created_at": legacy.get("created_at") or "",
            "lang": legacy.get("lang") or "",
            "metrics": {
                "reply_count": legacy.get("reply_count"),
                "retweet_count": legacy.get("retweet_count"),
                "favorite_count": legacy.get("favorite_count"),
                "quote_count": legacy.get("quote_count"),
                "bookmark_count": legacy.get("bookmark_count"),
                "view_count": ((tweet.get("views") or {}).get("count")),
            },
        }

    def _normalized_tweets_from_payload(self, payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        tweets = self._walk(payload)
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in tweets:
            normalized = self._normalize_tweet(item)
            if not normalized:
                continue
            key = normalized["id"]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(normalized)
            if len(deduped) >= limit:
                break
        return deduped

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise TwitterConfigurationError("Twitter source is disabled. Set X_SOURCE_ENABLED=true.")
        if not self._pool.states:
            raise TwitterConfigurationError("No Twitter sessions loaded. Check X_SESSIONS_FILE.")

    def fetch_profile_timeline(self, handle: str, limit: int = 10) -> dict[str, Any]:
        self._ensure_enabled()
        normalized_handle = (handle or "").strip().lstrip("@")
        if not normalized_handle:
            raise ValueError("handle is required")
        limit = max(1, min(50, int(limit or 10)))

        lookup = self._graphql_get(
            operation_name="UserByScreenName",
            query_id=self.query_user_by_screen_name,
            variables={"screen_name": normalized_handle, "withSafetyModeUserFields": True},
        )
        user_result = ((((lookup.get("data") or {}).get("user") or {}).get("result") or {}))
        user_rest_id = user_result.get("rest_id")
        user_legacy = user_result.get("legacy") or {}
        if not user_rest_id:
            raise TwitterUpstreamError(f"Failed to resolve handle @{normalized_handle}", status_code=404)

        timeline = self._graphql_get(
            operation_name="UserTweets",
            query_id=self.query_user_tweets,
            variables={
                "userId": user_rest_id,
                "count": limit,
                "includePromotedContent": False,
                "withQuickPromoteEligibilityTweetFields": True,
                "withVoice": True,
                "withV2Timeline": True,
            },
        )
        posts = self._normalized_tweets_from_payload(timeline, limit=limit)
        return {
            "source": "x-api",
            "handle": f"@{normalized_handle}",
            "author_name": user_legacy.get("name") or "",
            "author_id": user_rest_id,
            "count": len(posts),
            "posts": posts,
        }

    def fetch_post(self, url_or_id: str) -> dict[str, Any]:
        self._ensure_enabled()
        tweet_id = self._extract_tweet_id(url_or_id)
        payload = self._graphql_get(
            operation_name="TweetResultByRestId",
            query_id=self.query_tweet_detail,
            variables={
                "tweetId": tweet_id,
                "withCommunity": True,
                "includePromotedContent": False,
                "withVoice": True,
            },
        )
        posts = self._normalized_tweets_from_payload(payload, limit=1)
        if not posts:
            raise TwitterUpstreamError(f"Tweet not found for id {tweet_id}", status_code=404)
        return {"source": "x-api", "post": posts[0]}

    def search_posts(self, query: str, limit: int = 10) -> dict[str, Any]:
        self._ensure_enabled()
        q = (query or "").strip()
        if not q:
            raise ValueError("query is required")
        if not self.query_search:
            raise TwitterConfigurationError("X_QUERY_SEARCH_TIMELINE is not configured.")
        limit = max(1, min(50, int(limit or 10)))
        payload = self._graphql_get(
            operation_name="SearchTimeline",
            query_id=self.query_search,
            variables={
                "rawQuery": q,
                "count": limit,
                "querySource": "typed_query",
                "product": "Latest",
            },
        )
        posts = self._normalized_tweets_from_payload(payload, limit=limit)
        return {"source": "x-api", "query": q, "count": len(posts), "posts": posts}


_twitter_source_service: TwitterSourceService | None = None


def get_twitter_source_service() -> TwitterSourceService:
    """Singleton accessor for Twitter source service."""
    global _twitter_source_service
    if _twitter_source_service is None:
        _twitter_source_service = TwitterSourceService()
    return _twitter_source_service

