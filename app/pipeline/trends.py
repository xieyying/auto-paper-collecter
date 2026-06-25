"""Hot-topic analysis: gather recent papers in a domain across every source,
cluster them into computer-science subfields with the LLM, count last-window vs
previous-window, pick Top 3, summarize each direction, and expose the papers
behind each direction so the UI can show "查看方向总结"."""
import json
import re
import asyncio
import datetime as dt
from collections import defaultdict

from ..sources import arxiv, semanticscholar, crossref
from ..pipeline.dedup import dedup
from ..services.ai import chat

LABEL_SYS = (
    "你是计算机科学研究分析助手。下面是若干论文标题。"
    "请把每篇归入一个【粗粒度】的计算机科学主流子领域（中文，4-10字），"
    "例如：自然语言处理、计算机视觉、强化学习、机器学习理论、系统与编译、"
    "信息安全、软件工程、机器人学、数据库与数据管理、计算机图形学、"
    "理论与算法、人机交互、计算机网络 等。"
    "务必合并近义方向、控制类别数量（整批尽量不超过 12 类），让每类聚集足够多的论文；"
    "不属于计算机科学或无法归类的填“其他”。"
    "严格只输出 JSON 数组，每项为 {\"i\": 序号, \"label\": \"子领域\"}，不要任何其它文字。"
)
SUMM_SYS = (
    "你是计算机科学研究分析助手。下面给出某子领域近期的多篇论文标题。"
    "请写一段更详细的方向总结（简体中文，3-5 句、约 120-180 字）："
    "①该方向当前的研究焦点是什么；②主流技术路线/方法趋势；③代表性工作或反复出现的共性主题。"
    "用连贯的段落表达，不要分点符号、不要罗列编号。只输出这段话。"
)

# Labels that mean "couldn't classify" — never shown as a real hot direction.
_SKIP = {"其他", "未知", "无", "other", "others", "unknown", "misc", "n/a", "na", ""}


async def _collect(domain: str, days: int = 14):
    """Pull a broad, recent, cross-source sample for the domain, newest first.
    Drops Crossref's garbage future-dated records (e.g. year 2121)."""
    items = []
    for fn in (arxiv.search, semanticscholar.search, crossref.search):
        try:
            items.extend(await fn(domain, 80))
        except Exception:
            continue
    items = dedup(items)
    now = dt.datetime.utcnow()
    cutoff = now - dt.timedelta(days=days * 2)
    horizon = now + dt.timedelta(days=2)
    items = [it for it in items
             if it.published_at and cutoff <= it.published_at <= horizon]
    items.sort(key=lambda x: x.published_at, reverse=True)
    return items


_SRC_STYLE = {
    "arXiv": ("#B31B1B", "#FBEAEA"), "Google Scholar": ("#1A73E8", "#E8F0FE"),
    "IEEE": ("#00629B", "#E1EEF6"), "ACM": ("#0F6FB5", "#E3F0F8"),
    "Crossref": ("#5B6470", "#EEF1F5"), "学术新闻": ("#7C4DD9", "#F0EAFB"),
}


def _paper_card(it):
    c = _SRC_STYLE.get(it.source, _SRC_STYLE["Crossref"])
    d = it.published_at
    return {"title": it.title, "source": it.source, "url": it.url,
            "venue": it.venue or "", "sourceColor": c[0], "sourceBg": c[1],
            "published": d.strftime("%Y-%m-%d") if d else ""}


async def _label(items, batch_size: int = 20):
    """Return a CS-subfield label for each item (parallel-aligned list).

    The titles are labeled in small concurrent BATCHES. One big call would run
    past the gateway's ~100s Cloudflare limit and 524 (which silently turned
    every label into '其他' → zero hot directions)."""
    if not items:
        return []
    labels = ["其他"] * len(items)

    async def _label_batch(start, chunk):
        titles = "\n".join(f"{j}. {it.title}" for j, it in enumerate(chunk))
        raw = await chat(
            [{"role": "system", "content": LABEL_SYS}, {"role": "user", "content": titles}],
            temperature=0.2, max_tokens=1500, timeout=90,
        )
        if not raw:
            return
        m = re.search(r"\[.*\]", raw, re.S)
        if not m:
            return
        try:
            for obj in json.loads(m.group(0)):
                j = int(obj.get("i"))
                if 0 <= j < len(chunk):
                    labels[start + j] = str(obj.get("label", "其他")).strip() or "其他"
        except Exception:
            pass

    await asyncio.gather(*[
        _label_batch(start, items[start:start + batch_size])
        for start in range(0, len(items), batch_size)
    ])
    return labels


async def compute_trends(domain: str, window: int = 7):
    if not domain:
        return {"bars": [], "top3": []}
    items = await _collect(domain, window)
    items = items[:100]            # cap so the labeling call fits its token budget
    labels = await _label(items)

    now = dt.datetime.utcnow()
    last_cut = now - dt.timedelta(days=window)
    prev_cut = now - dt.timedelta(days=window * 2)

    last = defaultdict(int)
    prev = defaultdict(int)
    bucket_items = defaultdict(list)
    for it, lab in zip(items, labels):
        if lab.strip().lower() in _SKIP:          # drop the catch-all bucket
            continue
        d = it.published_at or dt.datetime.min
        if d >= last_cut:
            last[lab] += 1
            bucket_items[lab].append(it)
        elif d >= prev_cut:
            prev[lab] += 1

    rows = []
    for lab, cnt in last.items():
        p = prev.get(lab, 0)
        growth = round((cnt - p) / p * 100) if p else (100 if cnt else 0)
        rows.append({"name": lab, "en": "", "delta": cnt, "growth": growth})
    rows.sort(key=lambda r: r["delta"], reverse=True)

    # detailed LLM summary + the LATEST backing papers for the Top 3
    top3 = []
    for i, r in enumerate(rows[:3]):
        its = sorted(bucket_items.get(r["name"], []),
                     key=lambda x: x.published_at or dt.datetime.min, reverse=True)
        summary = ""
        if its:
            titles = [x.title for x in its[:12]]
            raw = await chat(
                [{"role": "system", "content": SUMM_SYS},
                 {"role": "user", "content": "方向：" + r["name"] + "\n" + "\n".join(titles)}],
                temperature=0.4, max_tokens=500,
            )
            summary = (raw or "").strip()
        if not summary:
            # Never surface "(暂无总结)": if the LLM is unavailable, synthesize a
            # summary from the actual papers so the panel always has content.
            reps = "；".join(x.title for x in its[:3]) if its else ""
            summary = (f"近 {window} 天该方向有 {r['delta']} 篇新论文。"
                       + (f"代表工作包括：{reps}。" if reps else ""))
        top3.append({**r, "rank": i + 1, "summary": summary,
                     "papers": [_paper_card(x) for x in its[:15]]})

    return {"bars": rows, "top3": top3}
