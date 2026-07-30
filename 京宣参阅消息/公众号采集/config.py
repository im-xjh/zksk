"""京宣公众号采集任务的配置加载与账号清单校验。"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ConfigurationError(ValueError):
    """采集任务配置无法安全运行。"""


DEFAULTS = {
    "EXPORTER_BASE_URL": "http://wechat-article-exporter:3000",
    "AUTH_COOKIE_DIR": "/exporter-kv-cookie",
    "ACCOUNTS_FILE": "/app/accounts.json",
    "STATE_DB": "/state/jingxuan_articles.sqlite3",
    "EXISTING_SYNC_DB": "/existing-sync-state/wechat_articles.sqlite3",
    "GITHUB_REPO": "im-xjh/zksk",
    "GITHUB_BRANCH": "main",
    "GITHUB_FEED_PATH": "docs/jingxuan/feed.json",
    "WINDOW_DAYS": "1",
    "INTERVAL_SECONDS": "600",
    "ACCOUNT_DELAY_SECONDS": "15",
    "TZ": "Asia/Shanghai",
}


@dataclass
class Config:
    github_token: str
    exporter_base_url: str
    auth_cookie_dir: Path
    accounts_file: Path
    state_db: Path
    existing_sync_db: Path
    github_repo: str
    github_branch: str
    github_feed_path: str
    window_days: int
    interval_seconds: int
    account_delay_seconds: int
    timezone: ZoneInfo
    accounts: list[dict]

    @classmethod
    def load(cls) -> "Config":
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            raise ConfigurationError("GITHUB_TOKEN 未设置")

        accounts_file = Path(_value("ACCOUNTS_FILE"))
        accounts = _load_accounts(accounts_file)
        try:
            timezone = ZoneInfo(_value("TZ"))
        except ZoneInfoNotFoundError as error:
            raise ConfigurationError("TZ 无法识别") from error

        return cls(
            github_token=token,
            exporter_base_url=_value("EXPORTER_BASE_URL"),
            auth_cookie_dir=Path(_value("AUTH_COOKIE_DIR")),
            accounts_file=accounts_file,
            state_db=Path(_value("STATE_DB")),
            existing_sync_db=Path(_value("EXISTING_SYNC_DB")),
            github_repo=_value("GITHUB_REPO"),
            github_branch=_value("GITHUB_BRANCH"),
            github_feed_path=_value("GITHUB_FEED_PATH"),
            window_days=_window_days(),
            interval_seconds=_positive_int("INTERVAL_SECONDS"),
            account_delay_seconds=_nonnegative_int("ACCOUNT_DELAY_SECONDS"),
            timezone=timezone,
            accounts=accounts,
        )

    def validate_accounts(self) -> None:
        _validate_accounts(self.accounts)


def _value(name: str) -> str:
    return os.getenv(name, DEFAULTS[name])


def _positive_int(name: str) -> int:
    return _integer(name, minimum=1)


def _window_days() -> int:
    if _value("WINDOW_DAYS") != "1":
        raise ConfigurationError("WINDOW_DAYS 必须为 1")
    return 1


def _nonnegative_int(name: str) -> int:
    return _integer(name, minimum=0)


def _integer(name: str, minimum: int) -> int:
    try:
        value = int(_value(name))
    except ValueError as error:
        raise ConfigurationError(f"{name} 必须为整数") from error
    if value < minimum:
        raise ConfigurationError(f"{name} 超出允许范围")
    return value


def _load_accounts(path: Path) -> list[dict]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationError("账号清单无法读取") from error
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ConfigurationError("账号清单格式无效")
    return _normalize_accounts(manifest.get("accounts"))


def _normalize_accounts(accounts: object) -> list[dict]:
    if not isinstance(accounts, list) or not accounts:
        raise ConfigurationError("账号清单 accounts 不能为空")

    normalized_accounts = []
    for account in accounts:
        if not isinstance(account, dict):
            raise ConfigurationError("账号清单包含无效账号")
        name = account["nickname"] if "nickname" in account else account.get("name")
        fakeid = account.get("fakeid")
        if not isinstance(name, str) or not name.strip() or not isinstance(fakeid, str) or not fakeid.strip():
            raise ConfigurationError("账号缺少名称或 fakeid")
        normalized_accounts.append({"name": name.strip(), "fakeid": fakeid})

    _validate_accounts(normalized_accounts)
    return normalized_accounts


def _validate_accounts(accounts: object) -> None:
    if not isinstance(accounts, list) or not accounts:
        raise ConfigurationError("账号清单 accounts 不能为空")

    fakeids = set()
    for account in accounts:
        if not isinstance(account, dict):
            raise ConfigurationError("账号清单包含无效账号")
        name = account.get("name")
        fakeid = account.get("fakeid")
        if not isinstance(name, str) or not name.strip() or not isinstance(fakeid, str) or not fakeid.strip():
            raise ConfigurationError("账号缺少名称或 fakeid")
        if fakeid in fakeids:
            raise ConfigurationError("账号清单包含重复 fakeid")
        fakeids.add(fakeid)
