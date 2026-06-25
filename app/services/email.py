"""Simple SMTP email sender (stdlib). No-op if SMTP not configured."""
import json
import datetime as dt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ..config import settings
from ..models import Paper, UserSettings


def send_email(subject: str, html: str, to: str = ""):
    to = to or settings.EMAIL_TO or settings.SMTP_USER
    if not (settings.SMTP_HOST and settings.SMTP_USER and to):
        print("[email] SMTP not configured; skipping")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as srv:
            srv.starttls()
            srv.login(settings.SMTP_USER, settings.SMTP_PASS)
            srv.sendmail(msg["From"], [to], msg.as_string())
        print(f"[email] sent to {to}")
        return True
    except Exception as e:
        print(f"[email] failed: {e}")
        return False


def send_feed_digest(db, since_hours: int = 14) -> dict:
    """Email the recent feed to the user, if the email channel is enabled.
    Shared by the scheduler and the manual /api/refresh trigger. Never raises."""
    s = db.get(UserSettings, 1)
    if not s:
        return {"sent": False, "reason": "no settings"}
    channels = json.loads(s.channels or "{}")
    if not (channels.get("email") and s.email):
        return {"sent": False, "reason": "email channel off or no recipient"}
    since = dt.datetime.utcnow() - dt.timedelta(hours=since_hours)
    papers = (db.query(Paper).filter(Paper.fetched_at >= since)
              .order_by(Paper.published_at.desc()).limit(15).all())
    if not papers:
        return {"sent": False, "reason": "no recent papers in window"}
    data = [{"source": p.source, "topic": p.topic, "title": p.title,
             "url": p.url, "tldr": p.tldr} for p in papers]
    ok = send_email("ScholarPulse · 今日文献流", feed_digest_html(data), s.email)
    return {"sent": ok, "to": s.email, "count": len(papers),
            "reason": "" if ok else "SMTP not configured or send failed (见后端日志 [email])"}


def feed_digest_html(papers):
    rows = []
    for p in papers[:15]:
        rows.append(
            f'<div style="margin:0 0 16px;padding:0 0 16px;border-bottom:1px solid #eee">'
            f'<div style="font-size:12px;color:#888">{p.get("source","")} · {p.get("topic","")}</div>'
            f'<a href="{p.get("url","#")}" style="font-size:16px;color:#16181D;text-decoration:none;font-weight:600">{p.get("title","")}</a>'
            f'<div style="font-size:13px;color:#555;margin-top:6px">{p.get("tldr","")}</div></div>'
        )
    return (
        '<div style="font-family:sans-serif;max-width:620px;margin:0 auto">'
        '<h2 style="color:#2A5BD7">ScholarPulse · 今日文献</h2>' + "".join(rows) + "</div>"
    )
