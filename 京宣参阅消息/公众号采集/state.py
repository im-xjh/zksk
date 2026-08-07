"""公众号采集的本地去重状态。"""

from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from typing import Iterable

from models import Article


def open_state(path: Path) -> sqlite3.Connection:
    """打开并初始化文章去重状态数据库。"""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            url TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            account_name TEXT NOT NULL,
            fakeid TEXT NOT NULL,
            aid TEXT NOT NULL,
            published_at TEXT NOT NULL,
            publish_ts INTEGER NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def upsert_articles(
    conn: sqlite3.Connection, articles: Iterable[Article], seen_at: str
) -> tuple[int, int]:
    """写入文章，并返回新增数与已存在文章数。"""
    inserted = 0
    updated = 0
    for article in articles:
        exists = conn.execute(
            "SELECT 1 FROM articles WHERE url = ?", (article.url,)
        ).fetchone()
        conn.execute(
            """
            INSERT INTO articles (
                url, title, summary, account_name, fakeid, aid, published_at,
                publish_ts, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title = excluded.title,
                summary = excluded.summary,
                account_name = excluded.account_name,
                fakeid = excluded.fakeid,
                aid = excluded.aid,
                published_at = excluded.published_at,
                publish_ts = excluded.publish_ts,
                last_seen_at = excluded.last_seen_at
            """,
            (
                article.url,
                article.title,
                article.summary,
                article.account_name,
                article.fakeid,
                article.aid,
                article.published_at,
                article.publish_ts,
                seen_at,
                seen_at,
            ),
        )
        if exists is None:
            inserted += 1
        else:
            updated += 1
    conn.commit()
    return inserted, updated


def recent_rows(conn: sqlite3.Connection, cutoff_ts: int) -> list[sqlite3.Row]:
    """读取时间窗口内的文章。"""
    return conn.execute(
        """
        SELECT * FROM articles
        WHERE publish_ts >= ?
        ORDER BY publish_ts DESC, url DESC
        """,
        (cutoff_ts,),
    ).fetchall()


def existing_sync_active(db_path: Path, now: datetime) -> bool:
    """判断既有采集任务是否仍在两小时保护期内。"""
    if not db_path.is_file():
        return False

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute(
            """
            SELECT started_at FROM runs
            WHERE finished_at IS NULL
            ORDER BY started_at DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return False
    started_at = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
    return started_at >= now - timedelta(hours=2)
