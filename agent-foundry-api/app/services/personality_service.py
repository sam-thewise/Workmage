"""Personality profile analysis from tweet text."""
from __future__ import annotations

from app.services.llm_service import completion


PERSONALITY_SYSTEM = """You are an expert at inferring writing voice and stance from social media posts.

Given a sample of someone's tweets (or post content), produce a short "personality profile" that content generators can use to match their voice. Include:

1. Tone and style (e.g. casual, technical, witty, earnest, sarcastic).
2. Do's: what they tend to do (e.g. ask questions, share links, use short sentences).
3. Don'ts: what to avoid (e.g. corporate speak, excessive hashtags, being preachy).
4. Vocabulary and phrases: notable words or phrases they use.
5. Stance/beliefs (if evident): 1–2 sentences on themes they care about.

Keep the profile concise (one or two short paragraphs or a bullet list). Output only the profile text, no preamble. This will be used so that generated posts and replies sound like the person, not like a generic bot."""


def analyze_tweets_to_profile(tweet_text: str, model: str = "openai/gpt-5-mini", api_key: str | None = None) -> str:
    """Analyze a block of tweet text and return a personality/voice profile."""
    if not (tweet_text or "").strip():
        return ""
    messages = [
        {"role": "system", "content": PERSONALITY_SYSTEM},
        {"role": "user", "content": f"Analyze these tweets and produce the personality profile:\n\n{tweet_text.strip()}"},
    ]
    response = completion(model=model, messages=messages, api_key=api_key)
    if not response or not getattr(response, "choices", None):
        return ""
    content = response.choices[0].message.content if response.choices else ""
    return (content or "").strip()
