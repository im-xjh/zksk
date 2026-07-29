from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import build_feed, normalize_article


def article_row(title: str, published: datetime, url: str | None = None) -> dict:
    return {
        "url": url or f"https://example/{title}",
        "title": title,
        "summary": f"{title} summary",
        "account_name": "京宣",
        "fakeid": "fakeid-1",
        "aid": f"aid-{title}",
        "published_at": published.isoformat(),
        "publish_ts": int(published.timestamp()),
    }


def test_normalize_article_converts_exporter_fields_to_article():
    tz = ZoneInfo("Asia/Shanghai")
    raw = {
        "link": "https://example/article",
        "title": "文章标题",
        "digest": "文章摘要",
        "aid": "aid-1",
        "publish_time": 1785283200,
    }

    article = normalize_article(raw, {"name": "京宣", "fakeid": "fakeid-1"}, tz)

    assert article is not None
    assert article.url == "https://example/article"
    assert article.title == "文章标题"
    assert article.summary == "文章摘要"
    assert article.account_name == "京宣"
    assert article.fakeid == "fakeid-1"
    assert article.aid == "aid-1"
    assert article.published_at == "2026-07-29T08:00:00+08:00"
    assert article.publish_ts == 1785283200


def test_build_feed_keeps_exactly_last_ten_days():
    now = datetime(2026, 7, 29, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    rows = [
        article_row("inside", now - timedelta(days=9, hours=23)),
        article_row("boundary", now - timedelta(days=10)),
        article_row("outside", now - timedelta(days=10, seconds=1)),
        article_row("future", now + timedelta(seconds=1)),
    ]

    feed = build_feed(rows, now)

    assert [item["title"] for item in feed["articles"]] == ["inside", "boundary"]
    assert feed["version"] == 1
    assert feed["window_days"] == 10
    assert feed["generated_at"] == "2026-07-29T12:00:00+08:00"


def test_build_feed_deduplicates_url_and_sorts_newest_first():
    now = datetime(2026, 7, 29, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    rows = [
        article_row("older", now - timedelta(hours=2), url="https://example/1"),
        article_row("newer", now - timedelta(hours=1), url="https://example/2"),
        article_row("duplicate", now - timedelta(hours=3), url="https://example/2"),
    ]

    feed = build_feed(rows, now)

    assert [item["title"] for item in feed["articles"]] == ["newer", "older"]
    assert feed["article_count"] == 2
    assert set(feed["articles"][0]) == {
        "id",
        "account_name",
        "title",
        "summary",
        "published_at",
        "url",
    }
    assert "fakeid" not in feed["articles"][0]
    assert "aid" not in feed["articles"][0]
