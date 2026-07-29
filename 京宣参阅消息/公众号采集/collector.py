"""京宣公众号一轮采集、发布和定时调度。"""

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from pathlib import Path
import sys
import time
from typing import Callable

import requests

from config import Config, ConfigurationError
from exporter import SessionExpired, fetch_account, latest_auth_key
from github_feed import GitHubFeedClient
from models import build_feed
from state import existing_sync_active as state_existing_sync_active
from state import open_state, recent_rows, upsert_articles


LOGGER = logging.getLogger(__name__)


@dataclass
class RunReport:
    accounts_ok: int = 0
    account_errors: dict[str, str] = field(default_factory=dict)
    published: bool = False
    commit_sha: str | None = None
    skipped_reason: str | None = None
    session_expired: bool = False


@dataclass
class Dependencies:
    exporter_session: object
    state_factory: Callable[[Path], object]
    github_client_factory: Callable[[], object]
    clock: Callable[[], datetime]
    sleep: Callable[[float], None]
    auth_key_resolver: Callable[[Path], str] = latest_auth_key
    fetch_account_fn: Callable = fetch_account
    existing_sync_checker: Callable[[Path, datetime], bool] = state_existing_sync_active
    existing_sync_active: Callable[[Path, datetime], bool] | bool | None = None

    @property
    def exporter(self):
        return self.exporter_session

    @property
    def github(self):
        return self.github_client_factory()


def run_once(
    config: Config, initial: bool = False, deps: Dependencies | None = None
) -> RunReport:
    """执行一次安全的账号采集与 Feed 条件发布。"""
    config.validate_accounts()
    deps = deps or _default_dependencies(config)
    now = deps.clock().astimezone(config.timezone)
    sync_state = deps.existing_sync_active
    active = (
        sync_state(config.existing_sync_db, now)
        if callable(sync_state)
        else bool(sync_state)
        if sync_state is not None
        else deps.existing_sync_checker(config.existing_sync_db, now)
    )
    if active:
        LOGGER.info("京宣采集跳过 existing_sync_active")
        return RunReport(skipped_reason="existing_sync_active")

    auth_key = deps.auth_key_resolver(config.auth_cookie_dir)
    cutoff_ts = int((now - timedelta(days=config.window_days)).timestamp())
    conn = deps.state_factory(config.state_db)
    report = RunReport()
    try:
        for index, account in enumerate(config.accounts):
            try:
                articles = deps.fetch_account_fn(
                    deps.exporter_session,
                    config.exporter_base_url,
                    auth_key,
                    account,
                    cutoff_ts,
                    initial,
                    deps.sleep,
                )
                upsert_articles(conn, articles, now.isoformat())
                report.accounts_ok += 1
                LOGGER.info("京宣采集账号=%s articles=%d", account["name"], len(articles))
            except SessionExpired:
                LOGGER.error("京宣采集失败 error_class=SessionExpired")
                report.session_expired = True
                return report
            except Exception as error:
                error_class = type(error).__name__
                report.account_errors[account["name"]] = error_class
                LOGGER.error("京宣采集账号=%s error_class=%s", account["name"], error_class)

            if index < len(config.accounts) - 1 and config.account_delay_seconds:
                deps.sleep(config.account_delay_seconds)

        rows = recent_rows(conn, cutoff_ts)
        if report.accounts_ok == 0 and not rows:
            report.skipped_reason = "no_articles_after_account_failures"
            LOGGER.error("京宣采集不发布 accounts_ok=0 article_count=0")
            return report

        feed = build_feed(rows, now, config.window_days)
        feed["window_days"] = config.window_days
        result = deps.github_client_factory().publish_if_changed(
            config.github_feed_path, feed
        )
        report.published = result.changed
        report.commit_sha = result.commit_sha
        LOGGER.info(
            "京宣 Feed 发布 accounts_ok=%d account_errors=%d article_count=%d changed=%s commit_sha=%s",
            report.accounts_ok,
            len(report.account_errors),
            feed["article_count"],
            result.changed,
            result.commit_sha,
        )
        return report
    finally:
        conn.close()


def run_forever(config: Config, deps: Dependencies | None = None) -> None:
    """以固定起始间隔连续运行采集任务。"""
    deps = deps or _default_dependencies(config)
    while True:
        started = deps.clock()
        report = run_once(config, deps=deps)
        if report.session_expired:
            raise SessionExpired("导出器登录会话已失效")
        elapsed_seconds = (deps.clock() - started).total_seconds()
        deps.sleep(max(1, config.interval_seconds - elapsed_seconds))


def _default_dependencies(config: Config) -> Dependencies:
    return Dependencies(
        exporter_session=requests.Session(),
        state_factory=open_state,
        github_client_factory=lambda: GitHubFeedClient(
            token=config.github_token,
            repo=config.github_repo,
            branch=config.github_branch,
        ),
        clock=lambda: datetime.now(config.timezone),
        sleep=time.sleep,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="京宣公众号采集")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate-accounts")
    once = subcommands.add_parser("once")
    once.add_argument("--initial", action="store_true")
    subcommands.add_parser("run")
    args = parser.parse_args(argv)

    try:
        config = Config.load()
        if args.command == "validate-accounts":
            print(f"账号清单校验通过：{len(config.accounts)} 个账号")
            return 0
        if args.command == "once":
            report = run_once(config, initial=args.initial)
            return _exit_status(report)
        run_forever(config)
        return 0
    except (ConfigurationError, SessionExpired) as error:
        print(f"采集任务失败：{type(error).__name__}", file=sys.stderr)
        return 1


def _exit_status(report: RunReport) -> int:
    if report.session_expired:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
