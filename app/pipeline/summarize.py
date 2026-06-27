"""Turn a raw paper into {tldr, method, contributions[]} via the LLM gateway.
Falls back to the source-provided TLDR / truncated abstract when AI is off."""
import json
import re
from ..services.ai import chat

SYS = (
    "你是科研助理。阅读论文标题与摘要，用简体中文输出严格的 JSON，"
    "不要任何额外文字。字段：tldr（一句话核心，<=60字）、"
    "method（方法简述，<=80字）、contributions（核心贡献数组，2-3条，每条<=30字）。"
)

_JSON = re.compile(r"\{.*\}", re.S)


def _fallback(item):
    tldr = item.tldr or (item.abstract[:80] + "…" if item.abstract else item.title)
    return {"tldr": tldr, "method": item.abstract[:160], "contributions": []}


async def summarize(item):
    if not item.abstract and not item.tldr:
        return _fallback(item)
    user = f"标题：{item.title}\n\n摘要：{item.abstract or item.tldr}"
    # summaries are non-critical → fail fast (shorter timeout, 1 retry) and fall
    # back to the source TLDR / abstract, so a flaky gateway can't stall a refresh.
    raw = await chat(
        [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
        temperature=0.2, max_tokens=500, timeout=45, retries=1,
    )
    if not raw:
        return _fallback(item)
    m = _JSON.search(raw)
    if not m:
        return _fallback(item)
    try:
        obj = json.loads(m.group(0))
        return {
            "tldr": str(obj.get("tldr", "")).strip() or _fallback(item)["tldr"],
            "method": str(obj.get("method", "")).strip(),
            "contributions": [str(c).strip() for c in (obj.get("contributions") or [])][:3],
        }
    except Exception:
        return _fallback(item)
