"""Unit tests for Twitter source helpers."""
from app.services.twitter_source import TwitterSourceService, XSession


def test_extract_tweet_id_from_url():
    assert TwitterSourceService._extract_tweet_id("https://x.com/someone/status/1234567890") == "1234567890"


def test_extract_tweet_id_from_id():
    assert TwitterSourceService._extract_tweet_id("987654321") == "987654321"


def test_parse_session_jsonl_line():
    parsed = XSession.from_jsonl_line(
        '{"kind":"cookie","auth_token":"aaa","ct0":"bbb","username":"tester","id":"42"}'
    )
    assert parsed is not None
    assert parsed.auth_token == "aaa"
    assert parsed.ct0 == "bbb"
    assert parsed.username == "tester"
    assert parsed.account_id == "42"

