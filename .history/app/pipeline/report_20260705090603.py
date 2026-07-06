"""Weekly report: aggregate the past 7 days into picks + per-keyword summaries."""
import json
import datetime as dt
from collections import defaultdict

from ..db import SessionLocal
from ..models import Paper, UserSettings, WeeklyReport
from ..services.ai import chat

SECTION_SYS = (
    "你是科研分析助手。根据某关键词方向下本周的多篇论文标题，用简体中文写一段方向小结"
    "（2-3句，<=120字），概括本周该方向的研究热点与趋势。只输出这段话。"
)


def _iso_week_label(d):
    y, w, _ = d.isocalendar()
    start = d - dt.timedelta(days=d.weekday())
    end = start + dt.timedelta(days=6)
    return (f"{start.year}年{start.month}月{start.day}日 – {end.month}月{end.day}日", w)


async def build_weekly_report():
    db = SessionLocal()
    try:
        s = db.get(UserSettings, 1)
        keywords = json.loads(s.keywords or "[]") if s else []
        since = dt.datetime.utcnow() - dt.timedelta(days=7)
        papers = (db.query(Paper)
                  .filter(Paper.published_at >= since)
                  .order_by(Paper.published_at.desc()).all())

        by_topic = defaultdict(list)
        for p in papers:
            by_topic[p.topic].append(p)

        # picks: top 3 most recent with a tldr
        picks = []
        for p in papers[:3]:
            picks.append({
                "id": p.id, "source": p.source, "topic": p.topic,
                "title": p.title, "why": p.tldr or (p.abstract[:80] + "…" if p.abstract else ""),
            })

        sections = []
        for kw in keywords:
            group = by_topic.get(kw, [])
            text = ""
            if group:
                raw = await chat(
                    [{"role": "system", "content": SECTION_SYS},
                     {"role": "user", "content": "方向：" + kw + "\n" + "\n".join(g.title for g in group[:10])}],
                    temperature=0.4, max_tokens=300,
                )
                text = (raw or "").strip()
            sections.append({"name": kw, "count": len(group), "text": text})

        label, wk = _iso_week_label(dt.datetime.utcnow())
        data = {
            "week_label": label, "week_no": wk,
            "total": len(papers), "sources": len({p.source for p in papers}),
            "picks": picks, "sections": sections,
        }
        rep = WeeklyReport(week_label=label, data=json.dumps(data, ensure_ascii=False))
        db.add(rep); db.commit()
        return data
    finally:
        db.close()
