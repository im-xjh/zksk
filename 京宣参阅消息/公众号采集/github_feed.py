"""GitHub Contents API 的京宣公开 Feed 发布客户端。"""

import base64
from dataclasses import dataclass
import json
from urllib.parse import quote

import requests


class GitHubFeedError(RuntimeError):
    """GitHub Contents API 返回非预期结果。"""


@dataclass(frozen=True)
class PublishResult:
    changed: bool
    commit_sha: str | None


class GitHubFeedClient:
    def __init__(
        self,
        token: str,
        repo: str,
        branch: str = "main",
        session: requests.Session | None = None,
    ):
        self._token = token
        self.repo = repo
        self.branch = branch
        self.session = session or requests.Session()
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
        }

    def get_feed(self, path: str) -> tuple[dict | None, str | None]:
        """读取现有 Feed，文件尚未创建时返回空值。"""
        response = self.session.get(
            self._contents_url(path),
            headers=self.headers,
            params={"ref": self.branch},
            timeout=30,
        )
        if response.status_code == 404:
            return None, None
        if response.status_code != 200:
            self._raise_api_error(response)

        payload = response.json()
        try:
            content = base64.b64decode(payload["content"]).decode("utf-8")
            return json.loads(content), payload["sha"]
        except (KeyError, TypeError, UnicodeDecodeError, ValueError) as error:
            raise GitHubFeedError("GitHub Contents API 返回的 Feed 无法解析") from error

    def publish_if_changed(self, path: str, feed: dict) -> PublishResult:
        """仅在文章窗口或文章列表变化时写入 GitHub。"""
        remote_feed, blob_sha = self.get_feed(path)
        if remote_feed is not None and self._same_content(remote_feed, feed):
            return PublishResult(changed=False, commit_sha=None)

        content = json.dumps(feed, ensure_ascii=False, indent=2) + "\n"
        payload = {
            "message": "更新京宣公众号文章列表",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": self.branch,
        }
        if blob_sha is not None:
            payload["sha"] = blob_sha

        response = self.session.put(
            self._contents_url(path),
            headers=self.headers,
            json=payload,
            timeout=30,
        )
        if response.status_code not in (200, 201):
            self._raise_api_error(response)

        try:
            return PublishResult(changed=True, commit_sha=response.json()["commit"]["sha"])
        except (KeyError, TypeError, ValueError) as error:
            raise GitHubFeedError("GitHub Contents API 返回的提交信息无法解析") from error

    def _contents_url(self, path: str) -> str:
        return (
            "https://api.github.com/repos/"
            f"{quote(self.repo, safe='/')}/contents/{quote(path, safe='/')}"
        )

    @staticmethod
    def _same_content(remote_feed: dict, feed: dict) -> bool:
        return (
            remote_feed.get("window_days") == feed.get("window_days")
            and remote_feed.get("articles") == feed.get("articles")
        )

    def _raise_api_error(self, response) -> None:
        body = response.text
        if self._token:
            body = body.replace(self._token, "[REDACTED]")
        body = body[:500]
        raise GitHubFeedError(f"GitHub Contents API 请求失败：{body}")
