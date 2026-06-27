"""Push the daily digest to optional channels — Telegram, Slack, and WeChat
(via Server酱 / ServerChan). All credentials come from environment variables;
each sender no-ops gracefully if its channel isn't configured."""
import httpx
from ..config import settings


def digest_text(papers, title="📚 文献雷达 · 今日文献"):
    lines = [title, ""]
    for p in papers[:15]:
        lines.append(f"• {p.get('title', '')}")
        if p.get("tldr"):
            lines.append(f"  {p['tldr']}")
        if p.get("url"):
            lines.append(f"  {p['url']}")
        lines.append("")
    return "\n".join(lines).strip()


async def send_telegram(text):
    tok = settings.TELEGRAM_BOT_TOKEN
    chat = settings.TELEGRAM_CHAT_ID
    if not (tok and chat):
        return {"sent": False, "reason": "Telegram 未配置（TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID）"}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                             json={"chat_id": chat, "text": text, "disable_web_page_preview": True})
            r.raise_for_status()
        return {"sent": True}
    except Exception as e:
        return {"sent": False, "reason": str(e)}


async def send_slack(text):
    url = settings.SLACK_WEBHOOK_URL
    if not url:
        return {"sent": False, "reason": "Slack 未配置（SLACK_WEBHOOK_URL）"}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(url, json={"text": text})
            r.raise_for_status()
        return {"sent": True}
    except Exception as e:
        return {"sent": False, "reason": str(e)}


async def send_wechat(text, title="文献雷达 · 今日文献"):
    """WeChat push, two ways (try in order):
      A) 企业微信群机器人 (WECHAT_WEBHOOK) — recommended; a group robot webhook,
         no third-party signup. Get it from a WeChat Work group → 添加群机器人.
      B) Server酱 (SERVERCHAN_KEY, like 'SCTxxxx') — pushes to your personal WeChat
         via https://sct.ftqq.com."""
    hook = settings.WECHAT_WEBHOOK
    if hook:
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(hook, json={"msgtype": "text",
                                             "text": {"content": (title + "\n\n" + text)[:2000]}})
                r.raise_for_status()
            return {"sent": True, "via": "企业微信群机器人"}
        except Exception as e:
            return {"sent": False, "reason": f"企业微信: {e}"}
    key = settings.SERVERCHAN_KEY
    if key:
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(f"https://sctapi.ftqq.com/{key}.send",
                                 data={"title": title, "desp": text})
                r.raise_for_status()
            return {"sent": True, "via": "Server酱"}
        except Exception as e:
            return {"sent": False, "reason": f"Server酱: {e}"}
    return {"sent": False, "reason": "微信未配置（企业微信 WECHAT_WEBHOOK 或 Server酱 SERVERCHAN_KEY 二选一）"}


async def push_all(papers, channels):
    """Send the digest to every enabled+configured channel. `channels` is the
    user's settings dict, e.g. {'telegram': True, 'slack': False, 'wechat': True}."""
    text = digest_text(papers)
    out = {}
    if channels.get("telegram"):
        out["telegram"] = await send_telegram(text)
    if channels.get("slack"):
        out["slack"] = await send_slack(text)
    if channels.get("wechat"):
        out["wechat"] = await send_wechat(text)
    return out
