from datetime import datetime
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import Article
from state import existing_sync_active, open_state, recent_rows, upsert_articles


NOW_ISO = "2026-07-29T09:30:00+08:00"


def make_article(url: str, title: str = "文章标题") -> Article:
    return Article(
        url=url,
        title=title,
        summary="文章摘要",
        account_name="京宣",
        fakeid="fakeid-1",
        aid="aid-1",
        published_at="2026-07-29T08:00:00+08:00",
        publish_ts=1785283200,
    )


def build_existing_runs_db(
    path: Path, started_at: str, finished_at: str | None
) -> Path:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE runs (started_at TEXT NOT NULL, finished_at TEXT)"
    )
    conn.execute(
        "INSERT INTO runs (started_at, finished_at) VALUES (?, ?)",
        (started_at, finished_at),
    )
    conn.commit()
    conn.close()
    return path


def test_upsert_articles_is_idempotent(tmp_path):
    conn = open_state(tmp_path / "state.sqlite3")
    article = make_article(url="https://example/1")

    assert upsert_articles(conn, [article], NOW_ISO) == (1, 0)
    assert upsert_articles(conn, [article], NOW_ISO) == (0, 1)
    assert len(recent_rows(conn, 0)) == 1


def test_upsert_articles_refreshes_existing_display_fields(tmp_path):
    conn = open_state(tmp_path / "state.sqlite3")
    original = make_article(url="https://example/1")
    refreshed = make_article(url="https://example/1", title="更新后的标题")

    upsert_articles(conn, [original], "2026-07-29T09:00:00+08:00")
    upsert_articles(conn, [refreshed], NOW_ISO)

    row = recent_rows(conn, 0)[0]
    assert row["title"] == "更新后的标题"
    assert row["first_seen_at"] == "2026-07-29T09:00:00+08:00"
    assert row["last_seen_at"] == NOW_ISO


def test_existing_sync_active_only_for_recent_unfinished_run(tmp_path):
    db = build_existing_runs_db(
        tmp_path / "wechat_articles.sqlite3",
        started_at="2026-07-29T01:00:00Z",
        finished_at=None,
    )
    now = datetime(2026, 7, 29, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert existing_sync_active(db, now) is True


def test_existing_sync_active_ignores_old_finished_and_missing_databases(tmp_path):
    now = datetime(2026, 7, 29, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    old_db = build_existing_runs_db(
        tmp_path / "old.sqlite3",
        started_at="2026-07-28T23:00:00Z",
        finished_at=None,
    )
    finished_db = build_existing_runs_db(
        tmp_path / "finished.sqlite3",
        started_at="2026-07-29T01:00:00Z",
        finished_at="2026-07-29T01:10:00Z",
    )

    assert existing_sync_active(old_db, now) is False
    assert existing_sync_active(finished_db, now) is False
    assert existing_sync_active(tmp_path / "missing.sqlite3", now) is False
