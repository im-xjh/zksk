"""公众号文章的规范化与公开 Feed 构造。"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Article:
    url: str
    title: str
    summary: str
    account_name: str
    fakeid: str
    aid: str
    published_at: str
    publish_ts: int


def normalize_article(raw: dict, account: dict, tz: ZoneInfo) -> Article | None:
    """将导出器文章记录转换为内部文章模型。"""
    url = raw.get("url") or raw.get("link")
    title = raw.get("title")
    publish_ts = raw.get("publish_ts")
    if publish_ts is None:
        publish_ts = raw.get("publish_time")
    if not url or not title or publish_ts is None:
        return None

    try:
        timestamp = int(publish_ts)
    except (TypeError, ValueError):
        return None

    return Article(
        url=str(url),
        title=str(title),
        summary=str(raw.get("summary") or raw.get("digest") or ""),
        account_name=str(account["name"]),
        fakeid=str(account["fakeid"]),
        aid=str(raw.get("aid") or ""),
        published_at=datetime.fromtimestamp(timestamp, tz).isoformat(),
        publish_ts=timestamp,
    )


def public_article(article: Article) -> dict:
    return {
        "id": hashlib.sha256(article.url.encode("utf-8")).hexdigest()[:16],
        "account_name": article.account_name,
        "title": article.title,
        "summary": article.summary,
        "published_at": article.published_at,
        "url": article.url,
    }


def build_feed(
    rows: Iterable[Mapping], now: datetime, window_days: int = 1
) -> dict:
    """保留时间窗口内的文章，按发布时间倒序去重后生成公开 Feed。"""
    if window_days != 1:
        raise ValueError("window_days 必须为 1")
    cutoff_ts = int((now - timedelta(days=window_days)).timestamp())
    now_ts = int(now.timestamp())
    articles = [
        Article(
            url=str(row["url"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            account_name=str(row["account_name"]),
            fakeid=str(row["fakeid"]),
            aid=str(row["aid"]),
            published_at=str(row["published_at"]),
            publish_ts=int(row["publish_ts"]),
        )
        for row in rows
        if cutoff_ts <= int(row["publish_ts"]) <= now_ts
    ]
    articles.sort(key=lambda article: (article.publish_ts, article.url), reverse=True)

    unique_articles = []
    seen_urls = set()
    for article in articles:
        if article.url in seen_urls:
            continue
        seen_urls.add(article.url)
        unique_articles.append(public_article(article))

    return {
        "version": 1,
        "generated_at": now.astimezone(ZoneInfo("Asia/Shanghai")).isoformat(),
        "window_days": window_days,
        "article_count": len(unique_articles),
        "articles": unique_articles,
    }
