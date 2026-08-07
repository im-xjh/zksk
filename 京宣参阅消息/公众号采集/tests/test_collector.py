from datetime import datetime, timedelta
import logging
from pathlib import Path
import json
import sys
from zoneinfo import ZoneInfo

import pytest
import requests


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config, ConfigurationError
from collector import AuthorizationKeyError, Dependencies, RunReport, main, run_forever, run_once
from exporter import FrequencyControlled, SessionExpired
from github_feed import GitHubFeedClient, GitHubFeedError, PublishResult
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
        self.fetch_calls = []

    def fetch(
        self,
        session,
        base_url,
        auth_key,
        account,
        cutoff_ts,
        initial,
        max_pages=10,
        sleep=None,
    ):
        self.fetch_calls.append(
            {
                "session": session,
                "base_url": base_url,
                "auth_key": auth_key,
                "max_pages": max_pages,
                "sleep": sleep,
            }
        )
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


class StopScheduler(Exception):
    pass


class FailingGitHubHTTP:
    def __init__(self, error):
        self.error = error

    def get(self, url, headers, params, timeout):
        raise self.error


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
        window_days=1,
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
        fetch_account_fn=exporter.fetch,
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
    assert [call["max_pages"] for call in deps.exporter.fetch_calls] == [10, 10]
    assert all(call["sleep"] is deps.sleep for call in deps.exporter.fetch_calls)


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
        [{"nickname": "A", "fakeid": "same"}, {"nickname": "B", "fakeid": "same"}],
        [{"nickname": "A"}],
    ],
)
def test_config_load_rejects_duplicate_or_missing_fakeid(tmp_path, monkeypatch, accounts):
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(json.dumps({"version": 1, "accounts": accounts}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("ACCOUNTS_FILE", str(accounts_file))

    with pytest.raises(ConfigurationError):
        Config.load()


def load_config(tmp_path, monkeypatch, accounts, *, window_days=None):
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(
        json.dumps({"version": 1, "accounts": accounts}), encoding="utf-8"
    )
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("ACCOUNTS_FILE", str(accounts_file))
    if window_days is not None:
        monkeypatch.setenv("WINDOW_DAYS", window_days)
    return Config.load()


@pytest.mark.parametrize(
    "window_days", ["10", "0", "01", "+1", " 1", "not-an-integer-secret"]
)
def test_config_load_rejects_window_days_other_than_one_without_echoing_value(
    tmp_path, monkeypatch, window_days
):
    with pytest.raises(ConfigurationError) as error:
        load_config(
            tmp_path,
            monkeypatch,
            [{"nickname": "京宣", "fakeid": "fakeid-1"}],
            window_days=window_days,
        )

    assert str(error.value) == "WINDOW_DAYS 必须为 1"


def test_config_load_accepts_window_days_one(tmp_path, monkeypatch):
    config = load_config(
        tmp_path,
        monkeypatch,
        [{"nickname": "京宣", "fakeid": "fakeid-1"}],
        window_days="1",
    )

    assert config.window_days == 1


def test_config_load_normalizes_canonical_nickname_to_collector_name(tmp_path, monkeypatch):
    config = load_config(
        tmp_path,
        monkeypatch,
        [{"nickname": "京宣", "fakeid": "fakeid-1"}],
    )

    assert config.accounts == [{"name": "京宣", "fakeid": "fakeid-1"}]


@pytest.mark.parametrize(
    "account",
    [
        {"name": "旧名称", "fakeid": "fakeid-1"},
        {"nickname": "规范名称", "name": "旧名称", "fakeid": "fakeid-1"},
        {"nickname": "规范名称", "fakeid": "fakeid-1", "articles": []},
        {"nickname": "规范名称", "fakeid": "fakeid-1", "completed": True},
    ],
)
def test_config_load_rejects_noncanonical_account_fields(
    tmp_path, monkeypatch, account
):
    with pytest.raises(ConfigurationError) as error:
        load_config(tmp_path, monkeypatch, [account])

    assert str(error.value) == "账号清单字段无效"


@pytest.mark.parametrize(
    "account",
    [
        {"fakeid": "fakeid-1"},
        {"nickname": " ", "fakeid": "fakeid-1"},
        {"nickname": "", "fakeid": "fakeid-1"},
    ],
)
def test_config_load_rejects_missing_or_blank_canonical_name(
    tmp_path, monkeypatch, account
):
    with pytest.raises(ConfigurationError):
        load_config(tmp_path, monkeypatch, [account])


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


def test_once_cli_hides_auth_key_path_on_resolver_failure(
    config, deps, monkeypatch, capsys
):
    sensitive_path = "/private/exporter-kv-cookie/current-auth-key"

    def fail_auth_key(_path):
        raise FileNotFoundError(sensitive_path)

    deps.auth_key_resolver = fail_auth_key
    monkeypatch.setattr("collector.Config.load", lambda: config)
    monkeypatch.setattr("collector._default_dependencies", lambda config: deps)

    assert main(["once"]) == 1
    assert sensitive_path not in capsys.readouterr().err


def test_once_cli_wraps_github_connection_failure_without_traceback(
    config, deps, monkeypatch, capsys
):
    sensitive_url = "https://api.github.test/secret-token/private-feed"
    deps.exporter_session.return_by_fakeid["a"] = [make_article("kept", hours_ago=1)]
    deps.github_client_factory = lambda: GitHubFeedClient(
        token="secret-token",
        repo="im-xjh/zksk",
        session=FailingGitHubHTTP(requests.exceptions.ConnectionError(sensitive_url)),
    )
    monkeypatch.setattr("collector.Config.load", lambda: config)
    monkeypatch.setattr("collector._default_dependencies", lambda config: deps)

    assert main(["once"]) == 1

    error_output = capsys.readouterr().err
    assert "GitHubFeedError" in error_output
    assert "Traceback" not in error_output
    assert sensitive_url not in error_output
    assert "secret-token" not in error_output


def test_run_once_reports_one_account_error_and_continues(deps, config):
    deps.exporter_session.errors_by_fakeid["a"] = RuntimeError("bad account")
    deps.exporter_session.return_by_fakeid["b"] = [make_article("kept", hours_ago=1)]

    report = run_once(config, deps=deps)

    assert report.accounts_ok == 1
    assert report.account_errors == {"账号 A": "RuntimeError"}
    assert report.published is True
    assert [item["title"] for item in deps.github_client_factory().last_feed["articles"]] == ["kept"]


def test_initial_run_with_account_failure_attempts_all_accounts_without_publication(
    deps, config
):
    deps.exporter_session.errors_by_fakeid["a"] = RuntimeError("bad account")
    deps.exporter_session.return_by_fakeid["b"] = [make_article("kept", hours_ago=1)]

    report = run_once(config, initial=True, deps=deps)

    assert deps.exporter_session.calls == ["a", "b"]
    assert report.account_errors == {"账号 A": "RuntimeError"}
    assert report.published is False
    assert report.skipped_reason == "initial_account_failures"
    assert deps.github_client_factory().last_feed is None


def test_initial_run_attempts_remaining_accounts_after_session_expiry_without_publication(
    deps, config
):
    deps.exporter_session.errors_by_fakeid["a"] = SessionExpired()
    deps.exporter_session.return_by_fakeid["b"] = [make_article("kept", hours_ago=1)]

    report = run_once(config, initial=True, deps=deps)

    assert deps.exporter_session.calls == ["a", "b"]
    assert report.account_errors == {"账号 A": "SessionExpired"}
    assert report.session_expired is True
    assert report.published is False
    assert report.skipped_reason == "initial_account_failures"
    assert deps.github_client_factory().last_feed is None


@pytest.mark.parametrize("argv", [["once"], ["once", "--initial"]])
def test_once_cli_returns_nonzero_after_account_failure(config, monkeypatch, argv):
    monkeypatch.setattr("collector.Config.load", lambda: config)
    monkeypatch.setattr(
        "collector.run_once",
        lambda config, initial=False: RunReport(account_errors={"账号 A": "RuntimeError"}),
    )

    assert main(argv) == 1


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


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(AuthorizationKeyError("sensitive-auth-key"), id="authorization"),
        pytest.param(SessionExpired("sensitive-cookie-path"), id="session"),
        pytest.param(GitHubFeedError("sensitive-response-body"), id="github"),
        pytest.param(FrequencyControlled("sensitive-frequency-detail"), id="frequency"),
    ],
)
def test_scheduler_keeps_cadence_after_predictable_run_failure_and_continues(
    config, monkeypatch, failure, caplog
):
    sleeps = []
    calls = []
    deps = Dependencies(
        exporter_session=FakeExporter(),
        state_factory=open_state,
        github_client_factory=FakeGitHubClient,
        clock=Clock(
            [
                NOW,
                NOW + timedelta(seconds=37),
                NOW + timedelta(seconds=600),
                NOW + timedelta(seconds=603),
            ]
        ),
        sleep=lambda seconds: sleeps.append(seconds),
    )

    def fake_run_once(config, initial=False, deps=None):
        calls.append(None)
        if len(calls) == 1:
            raise failure
        return RunReport()

    def stop_after_second_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise StopScheduler()

    deps.sleep = stop_after_second_sleep
    monkeypatch.setattr("collector.run_once", fake_run_once)
    caplog.set_level(logging.ERROR, logger="collector")

    with pytest.raises(StopScheduler):
        run_forever(config, deps=deps)

    assert len(calls) == 2
    assert sleeps == [563, 597]
    assert str(failure) not in caplog.text


def test_scheduler_keeps_cadence_after_reported_session_expiry_and_continues(
    config, monkeypatch
):
    sleeps = []
    reports = [RunReport(session_expired=True), RunReport()]
    deps = Dependencies(
        exporter_session=FakeExporter(),
        state_factory=open_state,
        github_client_factory=FakeGitHubClient,
        clock=Clock(
            [
                NOW,
                NOW + timedelta(seconds=37),
                NOW + timedelta(seconds=600),
                NOW + timedelta(seconds=603),
            ]
        ),
        sleep=lambda seconds: sleeps.append(seconds),
    )

    def stop_after_second_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise StopScheduler()

    deps.sleep = stop_after_second_sleep
    monkeypatch.setattr(
        "collector.run_once", lambda config, initial=False, deps=None: reports.pop(0)
    )

    with pytest.raises(StopScheduler):
        run_forever(config, deps=deps)

    assert sleeps == [563, 597]


def test_run_mode_sleeps_remaining_interval_after_github_timeout(
    config, deps, caplog
):
    sensitive_url = "https://api.github.test/secret-token/private-feed"
    sleeps = []
    deps.exporter_session.return_by_fakeid["a"] = [make_article("kept", hours_ago=1)]
    deps.github_client_factory = lambda: GitHubFeedClient(
        token="secret-token",
        repo="im-xjh/zksk",
        session=FailingGitHubHTTP(requests.exceptions.Timeout(sensitive_url)),
    )
    deps.clock = Clock([NOW, NOW, NOW + timedelta(seconds=37)])

    def stop_after_sleep(seconds):
        sleeps.append(seconds)
        raise StopScheduler()

    deps.sleep = stop_after_sleep
    caplog.set_level(logging.ERROR, logger="collector")

    with pytest.raises(StopScheduler):
        run_forever(config, deps=deps)

    assert sleeps == [563]
    assert sensitive_url not in caplog.text
    assert "secret-token" not in caplog.text
