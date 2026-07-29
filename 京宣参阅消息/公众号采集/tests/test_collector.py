from datetime import datetime, timedelta
from pathlib import Path
import json
import sqlite3
import sys
from zoneinfo import ZoneInfo

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config, ConfigurationError
from collector import Dependencies, RunReport, main, run_forever, run_once
from exporter import SessionExpired
from github_feed import PublishResult
from models import Article
from state import open_state


NOW = datetime(2026, 7, 29, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))


def make_article(title: str, *, hours_ago: int = 0, days_ago: int = 0) -> Article:
    published = NOW - timedelta(hours=hours_ago, days=days_ago)
    return Article(
        url=f"https://example.test/{title}",
        title=title,
        summary=f"{title} 摘要",
        account_name="",
        fakeid="",
        aid=f"aid-{title}",
        published_at=published.isoformat(),
        publish_ts=int(published.timestamp()),
    )


class FakeExporter:
    def __init__(self):
        self.return_by_fakeid = {}
        self.errors_by_fakeid = {}
        self.calls = []

    def fetch(self, account, cutoff_ts, initial, sleep):
        self.calls.append(account["fakeid"])
        error = self.errors_by_fakeid.get(account["fakeid"])
        if error:
            raise error
        articles = self.return_by_fakeid.get(account["fakeid"], [])
        return [
            Article(
                url=article.url,
                title=article.title,
                summary=article.summary,
                account_name=account["name"],
                fakeid=account["fakeid"],
                aid=article.aid,
                published_at=article.published_at,
                publish_ts=article.publish_ts,
            )
            for article in articles
        ]


class FakeGitHubClient:
    def __init__(self):
        self.last_feed = None

    def publish_if_changed(self, path, feed):
        self.last_feed = feed
        return PublishResult(changed=True, commit_sha="commit-sha")


class Clock:
    def __init__(self, values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


@pytest.fixture
def config(tmp_path):
    return Config(
        github_token="token",
        exporter_base_url="http://exporter.test",
        auth_cookie_dir=tmp_path / "cookies",
        accounts_file=tmp_path / "accounts.json",
        state_db=tmp_path / "state.sqlite3",
        existing_sync_db=tmp_path / "existing.sqlite3",
        github_repo="im-xjh/zksk",
        github_branch="main",
        github_feed_path="docs/jingxuan/feed.json",
        window_days=10,
        interval_seconds=600,
        account_delay_seconds=0,
        timezone=ZoneInfo("Asia/Shanghai"),
        accounts=[
            {"name": "账号 A", "fakeid": "a"},
            {"name": "账号 B", "fakeid": "b"},
        ],
    )


@pytest.fixture
def deps(tmp_path):
    exporter = FakeExporter()
    github = FakeGitHubClient()
    return Dependencies(
        exporter_session=exporter,
        state_factory=open_state,
        github_client_factory=lambda: github,
        clock=lambda: NOW,
        sleep=lambda seconds: None,
        auth_key_resolver=lambda path: "auth-key",
        fetch_account_fn=lambda session, base_url, auth_key, account, cutoff_ts, initial, sleep: session.fetch(account, cutoff_ts, initial, sleep),
        existing_sync_checker=lambda path, now: False,
    )


def test_run_once_publishes_recent_articles_in_account_order_independent_way(deps, config):
    deps.exporter.return_by_fakeid = {
        "a": [make_article("new", hours_ago=1)],
        "b": [make_article("old", days_ago=11)],
    }

    report = run_once(config, initial=True, deps=deps)

    assert report.accounts_ok == 2
    assert report.published is True
    assert [item["title"] for item in deps.github.last_feed["articles"]] == ["new"]


def test_run_once_skips_during_existing_daily_sync(deps, config):
    deps.existing_sync_active = True

    report = run_once(config, deps=deps)

    assert report.skipped_reason == "existing_sync_active"
    assert deps.exporter_session.calls == []


def test_run_once_rejects_empty_accounts_before_authentication_or_network(deps, config):
    config.accounts = []

    with pytest.raises(ConfigurationError, match="accounts"):
        run_once(config, deps=deps)

    assert deps.exporter_session.calls == []


@pytest.mark.parametrize(
    "accounts",
    [
        [{"name": "A", "fakeid": "same"}, {"name": "B", "fakeid": "same"}],
        [{"name": "A"}],
    ],
)
def test_config_load_rejects_duplicate_or_missing_fakeid(tmp_path, monkeypatch, accounts):
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(json.dumps({"version": 1, "accounts": accounts}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("ACCOUNTS_FILE", str(accounts_file))

    with pytest.raises(ConfigurationError):
        Config.load()


def test_session_expired_aborts_publication(deps, config):
    deps.exporter_session.errors_by_fakeid["a"] = SessionExpired()

    report = run_once(config, deps=deps)

    assert report.session_expired is True
    assert report.published is False
    assert deps.github_client_factory().last_feed is None
    assert deps.exporter_session.calls == ["a"]


def test_once_cli_returns_nonzero_after_session_expiry(config, monkeypatch):
    monkeypatch.setattr("collector.Config.load", lambda: config)
    monkeypatch.setattr(
        "collector.run_once", lambda config, initial=False: RunReport(session_expired=True)
    )

    assert main(["once"]) == 1


def test_run_once_reports_one_account_error_and_continues(deps, config):
    deps.exporter_session.errors_by_fakeid["a"] = RuntimeError("bad account")
    deps.exporter_session.return_by_fakeid["b"] = [make_article("kept", hours_ago=1)]

    report = run_once(config, deps=deps)

    assert report.accounts_ok == 1
    assert report.account_errors == {"账号 A": "RuntimeError"}
    assert report.published is True
    assert [item["title"] for item in deps.github_client_factory().last_feed["articles"]] == ["kept"]


def test_complete_account_failure_with_empty_state_does_not_publish(deps, config):
    deps.exporter_session.errors_by_fakeid = {"a": RuntimeError(), "b": RuntimeError()}

    report = run_once(config, deps=deps)

    assert report.accounts_ok == 0
    assert report.published is False
    assert report.skipped_reason == "no_articles_after_account_failures"
    assert deps.github_client_factory().last_feed is None


def test_scheduler_waits_until_ten_minutes_after_each_run_start(config, monkeypatch):
    started = NOW
    finished = NOW + timedelta(seconds=37)
    sleeps = []
    deps = Dependencies(
        exporter_session=FakeExporter(),
        state_factory=open_state,
        github_client_factory=FakeGitHubClient,
        clock=Clock([started, finished]),
        sleep=lambda seconds: (sleeps.append(seconds), (_ for _ in ()).throw(StopIteration)),
    )
    monkeypatch.setattr(
        "collector.run_once", lambda config, initial=False, deps=None: type("Report", (), {"session_expired": False})()
    )

    with pytest.raises(RuntimeError, match="generator raised StopIteration"):
        run_forever(config, deps=deps)

    assert sleeps == [563]
