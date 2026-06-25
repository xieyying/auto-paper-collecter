"""OpenAI-compatible chat client for the configured AI gateway."""
import asyncio
import httpx
from ..config import settings


async def chat(messages, temperature: float = 0.3, max_tokens: int = 900,
               timeout: float = 90, retries: int = 2):
    """Returns assistant text, or None if AI disabled / failed.

    Retries transient gateway hiccups (502/503/504/524 Cloudflare timeouts,
    429 rate limits) with a short backoff, since gateways can be flaky under load."""
    if not settings.AI_ENABLED or not settings.AI_API_KEY:
        return None
    url = settings.AI_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.AI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.AI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    last = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(url, headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            last = e
            if attempt < retries:
                await asyncio.sleep(1.5 * (attempt + 1))
    print(f"[ai] request failed after {retries + 1} tries: {last}")
    return None
