"""APScheduler jobs: twice-daily refresh (+ email digest) and weekly report."""
import json
import asyncio
import datetime as dt
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .db import SessionLocal
from .models import TrendSnapshot, Paper
from .pipeline.fetch import run_refresh, get_or_create_settings
from .pipeline.trends import compute_trends
from .pipeline.report import build_weekly_report
from .services.email import send_feed_digest
from .services import push

_scheduler = None


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def scheduled_refresh():
    print(f"[scheduler] refresh @ {dt.datetime.now():%H:%M}")
    _run_async(run_refresh())
    db = SessionLocal()
    try:
        s = get_or_create_settings(db)
        # Precompute trends so the dashboard's 热点 page opens instantly (cached).
        if s.domain:
            try:
                data = _run_async(compute_trends(s.domain, 7))
                if data and (data.get("top3") or data.get("bars")):
                    db.add(TrendSnapshot(domain=s.domain, window=7,
                                         data=json.dumps(data, ensure_ascii=False)))
                    db.commit()
                    print("[scheduler] trends precomputed")
            except Exception as e:
                print(f"[scheduler] trends precompute failed: {e}")
        # email digest if enabled (same helper the manual /api/refresh uses)
        status = send_feed_digest(db)
        print(f"[scheduler] digest email: {status}")
        # multi-channel push (Telegram / Slack / WeChat) if any is enabled
        channels = json.loads(s.channels or "{}")
        if any(channels.get(c) for c in ("telegram", "slack", "wechat")):
            since = dt.datetime.utcnow() - dt.timedelta(hours=14)
            papers = (db.query(Paper).filter(Paper.fetched_at >= since)
                      .order_by(Paper.published_at.desc()).limit(15).all())
            data = [{"title": p.title, "tldr": p.tldr, "url": p.url} for p in papers]
            if data:
                print(f"[scheduler] push: {_run_async(push.push_all(data, channels))}")
    finally:
        db.close()


def scheduled_weekly():
    print("[scheduler] weekly report")
    _run_async(build_weekly_report())


def start_scheduler():
    global _scheduler
    if _scheduler:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone=settings.TIMEZONE)
    db = SessionLocal()
    try:
        s = get_or_create_settings(db)
        times = [t.strip() for t in (s.refresh_times or settings.REFRESH_TIMES).split(",") if t.strip()]
    finally:
        db.close()
    for t in times:
        try:
            hh, mm = t.split(":")
            _scheduler.add_job(scheduled_refresh, CronTrigger(hour=int(hh), minute=int(mm)),
                               id=f"refresh_{t}", replace_existing=True)
        except Exception as e:
            print(f"[scheduler] bad time '{t}': {e}")
    # weekly report: Sunday 09:00
    _scheduler.add_job(scheduled_weekly, CronTrigger(day_of_week="sun", hour=9, minute=0),
                       id="weekly", replace_existing=True)
    _scheduler.start()
    print(f"[scheduler] started; refresh at {times}, tz={settings.TIMEZONE}")
    return _scheduler
