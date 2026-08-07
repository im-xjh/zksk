"""微信公众号文章导出器客户端。"""

import json
from pathlib import Path
import time
from typing import Callable
from zoneinfo import ZoneInfo

from models import Article, normalize_article


class SessionExpired(RuntimeError):
    """导出器登录会话已经失效。"""


class FrequencyControlled(RuntimeError):
    """导出器持续返回频率控制响应。"""


def latest_auth_key(cookie_dir: Path) -> str:
    """返回最近更新的授权键文件名。"""
    cookie_files = [path for path in cookie_dir.iterdir() if path.is_file()]
    if not cookie_files:
        raise FileNotFoundError(f"未找到授权键文件：{cookie_dir}")
    return max(
        cookie_files, key=lambda path: (path.stat().st_mtime_ns, path.name)
    ).name


def _fetch_page(session, base_url: str, auth_key: str, fakeid: str, begin: int, sleep):
    retry_waits = (5, 10, 20, 40)
    for wait in (*retry_waits, None):
        response = session.get(
            f"{base_url}/api/web/mp/appmsgpublish",
            headers={"X-Auth-Key": auth_key},
            params={"id": fakeid, "begin": begin, "size": 20},
            timeout=30,
        )
        payload = response.json()
        ret = payload.get("base_resp", {}).get("ret", 0)
        if ret == 0:
            return payload
        if ret == 200003:
            raise SessionExpired("导出器登录会话已失效")
        if ret == 200013:
            if wait is None:
                raise FrequencyControlled("导出器持续触发频率控制")
            sleep(wait)
            continue
        raise RuntimeError(f"导出器返回错误代码：{ret}")

    raise AssertionError("unreachable")


def _articles_from_page(payload: dict) -> list[dict]:
    publish_page = payload.get("publish_page", {})
    if isinstance(publish_page, str):
        publish_page = json.loads(publish_page)

    return [
        article
        for publish in publish_page.get("publish_list", [])
        for article in publish.get("publish_info", {}).get("appmsgex", [])
    ]


def fetch_account(
    session,
    base_url: str,
    auth_key: str,
    account: dict,
    cutoff_ts: int,
    initial: bool,
    max_pages: int = 10,
    sleep: Callable[[float], None] = time.sleep,
) -> list[Article]:
    """读取一个公众号的文章；首次运行从最新页翻至时间窗口边界。"""
    articles = []
    timezone = ZoneInfo("Asia/Shanghai")
    for begin in range(max_pages):
        payload = _fetch_page(
            session, base_url, auth_key, account["fakeid"], begin, sleep
        )
        raw_articles = _articles_from_page(payload)
        reached_cutoff = False
        for raw_article in raw_articles:
            article = normalize_article(raw_article, account, timezone)
            if article is None:
                continue
            if article.publish_ts < cutoff_ts:
                reached_cutoff = True
                continue
            articles.append(article)

        if not initial or reached_cutoff or not raw_articles:
            break
    return articles
