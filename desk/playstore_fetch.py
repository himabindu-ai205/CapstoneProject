from datetime import datetime, timedelta, timezone

from desk.schedule import CLOCK

APP_ID = "com.nextbillion.groww"
IST = timezone(timedelta(hours=5, minutes=30))


def fetch_playstore_reviews(start: datetime, end: datetime) -> list[dict]:
    from google_play_scraper import Sort, reviews

    token = None
    collected = []
    for _ in range(30):
        batch, token = reviews(
            APP_ID,
            lang="en",
            country="in",
            sort=Sort.NEWEST,
            count=200,
            continuation_token=token,
        )
        if not batch:
            break
        passed_the_week = False
        for item in batch:
            moment = item.get("at")
            if not isinstance(moment, datetime):
                continue
            created = _on_clock(moment)
            if created < start:
                passed_the_week = True
                continue
            if created > end:
                continue
            collected.append(_row(item, created))
        if passed_the_week or token is None:
            break
    return collected


def _on_clock(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return moment.astimezone(CLOCK)


def _row(item: dict, created: datetime) -> dict:
    replied = item.get("repliedAt")
    replied_at = ""
    if isinstance(replied, datetime):
        replied_at = _on_clock(replied).isoformat(timespec="seconds")
    return {
        "review_id": item.get("reviewId") or "",
        "created_at": created.isoformat(timespec="seconds"),
        "created_at_ist": created.astimezone(IST).isoformat(timespec="seconds"),
        "score": item.get("score") if item.get("score") is not None else "",
        "thumbs_up": item.get("thumbsUpCount") if item.get("thumbsUpCount") is not None else "",
        "app_version": item.get("reviewCreatedVersion") or "",
        "user_name": item.get("userName") or "",
        "content": item.get("content") or "",
        "developer_reply": item.get("replyContent") or "",
        "developer_replied_at": replied_at,
    }
