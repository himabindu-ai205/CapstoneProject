import csv
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from desk.guards import redact
from desk.reviews import _keep_review
from desk.schedule import CLOCK

WINDOW_WEEKS = 4
_THEMES = (
    ("Withdrawals & payouts", ("withdraw", "payout", "redeem")),
    ("Payments & UPI", ("upi", "payment")),
    ("Charges & fees", ("charge", "brokerage", "fee", "gst")),
    ("Trading & orders", ("trad", "order", "option", "broker", "intraday", "stock", "margin", "demat", "f&o")),
    ("General & praise", ()),
)
_GENERAL = "General & praise"
_ACTIONS = {
    "Trading & orders": ("Check order placement", "when a sell order does not go through during market moves"),
    "Charges & fees": ("Explain added charges", "that show up after an investment and take the wallet negative"),
    "Withdrawals & payouts": ("Shorten withdrawal approval", "so customers are not left waiting days for their money"),
    "Payments & UPI": ("Fix payment failures", "before the wrong amount leaves the account"),
    "General & praise": ("Read the general comments", "from this week before the next release"),
}


def default_data_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


def build_pulse(data_dir: Path | None = None) -> dict:
    rows = _load(data_dir or default_data_dir())
    grouped: dict = defaultdict(list)
    for row in rows:
        grouped[_monday(row["created"])].append(row)
    if not grouped:
        return _empty()
    pulse_monday = max(grouped)
    pulse_sunday = pulse_monday + timedelta(days=6)
    corpus_monday = pulse_monday - timedelta(days=7 * (WINDOW_WEEKS - 1))
    corpus_sunday = pulse_monday - timedelta(days=1)
    corpus_weeks = [corpus_monday + timedelta(days=7 * index) for index in range(WINDOW_WEEKS - 1)]
    chart_weeks = corpus_weeks + [pulse_monday]
    current_rows = _between(rows, pulse_monday, pulse_sunday)
    corpus_rows = _between(rows, corpus_monday, corpus_sunday)
    this_rating = _round(_average(current_rows))
    baseline = _round(_average(corpus_rows))
    delta = None if this_rating is None or baseline is None else round(this_rating - baseline, 1)
    themes = _themes(current_rows, grouped, corpus_weeks)
    shown = [theme for theme in themes if theme["count"] and theme["label"] != _GENERAL][:3]
    if len(shown) < 3:
        general = next((theme for theme in themes if theme["label"] == _GENERAL and theme["count"]), None)
        if general:
            shown.append(general)
    top = shown[0] if shown else None
    week_label = _range_label(pulse_monday, pulse_sunday)
    return {
        "ready": bool(current_rows or corpus_rows),
        "subtitle": week_label,
        "week_button": week_label,
        "synced": len(corpus_rows) + len(current_rows),
        "this_rating": _num(this_rating),
        "delta": delta,
        "delta_label": "—" if delta is None else f"{delta:+.1f} vs baseline",
        "baseline_label": "—" if baseline is None else f"corpus avg {_num(baseline)}",
        "this_count": len(current_rows),
        "corpus_count": len(corpus_rows),
        "corpus_weeks": len(corpus_weeks),
        "corpus_range": _range_label(corpus_monday, corpus_sunday),
        "chart_weeks": len(chart_weeks),
        "corpus_fill": 100 if corpus_rows else 0,
        "top": top,
        "weeks": _volume(chart_weeks, grouped, corpus_weeks),
        "ratings": _ratings(chart_weeks, grouped, baseline),
        "themes": shown,
        "shares": [theme for theme in themes if theme["count"]],
        "week_total": len(current_rows),
    }


def _load(data_dir: Path) -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for path, already_filtered in (
        (data_dir / "playstore_corpus.csv", True),
        (data_dir / "playstore.csv", False),
    ):
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for raw in csv.DictReader(handle):
                review_id = raw.get("review_id") or ""
                if not review_id or review_id in seen:
                    continue
                content = raw.get("content") or ""
                if not _keep_review(content):
                    continue
                if not already_filtered:
                    content = redact(content)
                created = _parse(raw.get("created_at") or "")
                if created is None:
                    continue
                seen.add(review_id)
                score = raw.get("score")
                rows.append(
                    {
                        "content": content,
                        "created": created,
                        "score": int(score) if score not in (None, "") else None,
                    }
                )
    return rows


def _themes(current: list[dict], grouped: dict, prior: list) -> list[dict]:
    buckets = {label: [] for label, _needles in _THEMES}
    for row in current:
        buckets[_theme(row["content"])].append(row)
    total = len(current)
    shares = _shares([len(buckets[label]) for label, _needles in _THEMES], total)
    themes = []
    for index, (label, _needles) in enumerate(_THEMES):
        rows = buckets[label]
        prior_counts = [sum(1 for row in grouped[start] if _theme(row["content"]) == label) for start in prior]
        prior_avg = sum(prior_counts) / len(prior_counts) if prior_counts else 0
        count = len(rows)
        if count > prior_avg:
            trend = "rising"
            arrow = "↑"
        elif count < prior_avg:
            trend = "easing"
            arrow = "↓"
        else:
            trend = "flat"
            arrow = "→"
        themes.append(
            {
                "label": label,
                "count": count,
                "share": shares[index],
                "rating": _num(_round(_average(rows))),
                "trend": trend,
                "arrow": arrow,
                "quote": _quote(rows),
                "action": _ACTIONS[label][0],
                "detail": _ACTIONS[label][1],
                "friction": label != _GENERAL,
            }
        )
    themes.sort(key=lambda theme: (-theme["count"], theme["label"]))
    return themes


def _theme(text: str) -> str:
    lowered = text.lower()
    for label, needles in _THEMES:
        if not needles:
            return label
        if any(_needle(lowered, needle) for needle in needles):
            return label
    return _GENERAL


def _needle(text: str, needle: str) -> bool:
    if needle == "f&o":
        return "f&o" in text or "f & o" in text
    if len(needle) <= 4:
        return re.search(rf"\b{re.escape(needle)}", text) is not None
    return needle in text


def _between(rows: list[dict], start, end) -> list[dict]:
    kept = []
    for row in rows:
        day = row["created"].astimezone(CLOCK).date()
        if start <= day <= end:
            kept.append(row)
    return kept


def _empty() -> dict:
    return {
        "ready": False,
        "subtitle": "No reviews in the corpus",
        "week_button": "No week",
        "synced": 0,
    }


def _volume(weeks: list, grouped: dict, baseline_weeks: list) -> dict:
    counts = [len(grouped.get(start, [])) for start in weeks]
    baseline_counts = [len(grouped.get(start, [])) for start in baseline_weeks]
    peak = max(counts) if counts else 0
    average = sum(baseline_counts) / len(baseline_counts) if baseline_counts else 0
    ymax = _ymax(max(peak, average, 1))
    left, right, bottom, top = 48, 545, 195, 28
    plot_h = bottom - top
    slot = (right - left) / len(weeks) if weeks else 1
    bar_w = min(44, slot * 0.55)
    bars = []
    for index, start in enumerate(weeks):
        count = counts[index]
        height = 0 if ymax == 0 else plot_h * count / ymax
        x = left + index * slot + (slot - bar_w) / 2
        bars.append(
            {
                "label": _day(start),
                "count": count,
                "x": round(x, 1),
                "y": round(bottom - height, 1),
                "h": round(height, 1),
                "w": round(bar_w, 1),
                "cx": round(x + bar_w / 2, 1),
                "current": index == len(weeks) - 1,
            }
        )
    baseline_y = round(bottom - plot_h * average / ymax, 1) if ymax else bottom
    ticks = []
    for value in (ymax, ymax / 2, 0):
        ticks.append({"label": str(int(value)), "y": round(bottom - plot_h * value / ymax, 1)})
    return {"bars": bars, "ticks": ticks, "baseline_y": baseline_y, "average": round(average, 1)}


def _range_label(start, end) -> str:
    if start.year == end.year:
        return f"{_day(start)} – {_day(end)} {end.year}"
    return f"{_day(start)} {start.year} – {_day(end)} {end.year}"


def _ratings(weeks: list, grouped: dict, baseline: float | None) -> dict:
    left, right, bottom, top = 36, 346, 116, 20
    plot_h = bottom - top
    step = (right - left) / (len(weeks) - 1) if len(weeks) > 1 else 0
    points = []
    labels = []
    for index, start in enumerate(weeks):
        rating = _average(grouped.get(start, []))
        x = left if len(weeks) == 1 else left + index * step
        labels.append({"label": _day(start), "x": round(x, 1), "current": index == len(weeks) - 1})
        if rating is None:
            continue
        y = bottom - plot_h * (rating / 5)
        points.append({"x": round(x, 1), "y": round(y, 1), "rating": _num(_round(rating)), "current": index == len(weeks) - 1})
    line = " ".join(f"{point['x']},{point['y']}" for point in points)
    area = ""
    if points:
        area = f"{points[0]['x']},{bottom} " + line + f" {points[-1]['x']},{bottom}"
    baseline_y = None if baseline is None else round(bottom - plot_h * (baseline / 5), 1)
    ticks = [{"label": label, "y": round(bottom - plot_h * (value / 5), 1)} for label, value in (("5", 5), ("3", 3), ("1", 1))]
    return {"points": points, "line": line, "area": area, "labels": labels, "baseline_y": baseline_y, "ticks": ticks}


def _shares(counts: list[int], total: int) -> list[int]:
    if total <= 0:
        return [0 for _count in counts]
    raw = [count * 100 / total for count in counts]
    floors = [int(value) for value in raw]
    spare = 100 - sum(floors)
    order = sorted(range(len(raw)), key=lambda index: raw[index] - floors[index], reverse=True)
    for index in order[:spare]:
        floors[index] += 1
    return floors


def _quote(rows: list[dict]) -> str:
    if not rows:
        return ""
    chosen = sorted(rows, key=lambda row: (row["score"] is None, row["score"] if row["score"] is not None else 99))[0]
    text = " ".join(chosen["content"].split())
    if len(text) <= 140:
        return text
    return text[:140].rsplit(" ", 1)[0] + "…"


def _average(rows: list[dict]) -> float | None:
    scores = [row["score"] for row in rows if row["score"] is not None]
    if not scores:
        return None
    return sum(scores) / len(scores)


def _ymax(value: float) -> int:
    for step in (5, 10, 20, 40, 60, 80, 100, 150, 200, 300, 500):
        if value <= step:
            return step
    return int(value) + 1


def _monday(moment: datetime):
    day = moment.astimezone(CLOCK).date()
    return day - timedelta(days=day.weekday())


def _parse(value: str) -> datetime | None:
    if not value:
        return None
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=CLOCK)
    return moment.astimezone(CLOCK)


def _span(rows: list[dict]) -> str:
    if not rows:
        return "No reviews in the corpus"
    moments = sorted(row["created"] for row in rows)
    start = _day(moments[0].astimezone(CLOCK).date())
    end = moments[-1].astimezone(CLOCK).date()
    if moments[0].astimezone(CLOCK).date() == end:
        return f"{start} {end.year}"
    return f"{start} – {_day(end)} {end.year}"


def _day(day) -> str:
    return f"{day.day} {day.strftime('%b')}"


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value + 1e-9, 1)


def _num(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}"
