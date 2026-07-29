import base64
import json
from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from github_feed import GitHubFeedClient, GitHubFeedError, PublishResult


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not JSON")
        return self._payload


class FakeHTTP:
    def __init__(self):
        self.get_response = None
        self.put_response = None
        self.get_calls = []
        self.put_calls = []

    def respond_get(self, remote, sha):
        content = base64.b64encode(
            json.dumps(remote, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        self.get_response = FakeResponse(200, {"content": content, "sha": sha})

    def respond_not_found(self):
        self.get_response = FakeResponse(404, {"message": "Not Found"})

    def respond_put(self, commit_sha):
        self.put_response = FakeResponse(201, {"commit": {"sha": commit_sha}})

    def get(self, url, headers, params, timeout):
        self.get_calls.append(
            {"url": url, "headers": headers, "params": params, "timeout": timeout}
        )
        return self.get_response

    def put(self, url, headers, json, timeout):
        self.put_calls.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return self.put_response


@pytest.fixture
def fake_http():
    return FakeHTTP()


@pytest.fixture
def client(fake_http):
    return GitHubFeedClient(
        token="secret-token", repo="im-xjh/zksk", session=fake_http
    )


def feed(article_ids, generated_at="2026-07-29T09:00:00+08:00"):
    return {
        "window_days": 10,
        "generated_at": generated_at,
        "article_count": len(article_ids),
        "articles": [{"id": article_id, "title": f"文章 {article_id}"} for article_id in article_ids],
    }


def test_publish_if_changed_skips_same_articles(client, fake_http):
    remote = feed(["a"], generated_at="old")
    fake_http.respond_get(remote, sha="blob-sha")

    result = client.publish_if_changed(
        "docs/jingxuan/feed.json", feed(["a"], generated_at="new")
    )

    assert result.changed is False
    assert fake_http.put_calls == []


def test_publish_if_changed_puts_changed_feed_with_sha(client, fake_http):
    fake_http.respond_get(feed(["a"]), sha="blob-sha")
    fake_http.respond_put(commit_sha="commit-sha")

    result = client.publish_if_changed("docs/jingxuan/feed.json", feed(["b"]))

    assert result == PublishResult(changed=True, commit_sha="commit-sha")
    assert fake_http.put_calls[0]["json"]["sha"] == "blob-sha"


def test_publish_if_changed_creates_feed_after_not_found(client, fake_http):
    fake_http.respond_not_found()
    fake_http.respond_put(commit_sha="initial-commit")

    result = client.publish_if_changed("docs/jingxuan/feed.json", feed(["a"]))

    assert result == PublishResult(changed=True, commit_sha="initial-commit")
    assert "sha" not in fake_http.put_calls[0]["json"]


def test_publish_if_changed_writes_utf8_pretty_json_with_newline(client, fake_http):
    fake_http.respond_not_found()
    fake_http.respond_put(commit_sha="commit-sha")
    payload = feed(["a"])
    payload["articles"][0]["title"] = "京宣文章"

    client.publish_if_changed("docs/jingxuan/feed.json", payload)

    encoded = fake_http.put_calls[0]["json"]["content"]
    assert base64.b64decode(encoded).decode("utf-8") == (
        '{\n'
        '  "window_days": 10,\n'
        '  "generated_at": "2026-07-29T09:00:00+08:00",\n'
        '  "article_count": 1,\n'
        '  "articles": [\n'
        '    {\n'
        '      "id": "a",\n'
        '      "title": "京宣文章"\n'
        '    }\n'
        '  ]\n'
        '}\n'
    )


def test_get_feed_quotes_repository_path(client, fake_http):
    fake_http.respond_get(feed(["a"]), sha="blob-sha")

    client.get_feed("docs/京宣 feed.json")

    assert fake_http.get_calls[0]["url"] == (
        "https://api.github.com/repos/im-xjh/zksk/contents/docs/"
        "%E4%BA%AC%E5%AE%A3%20feed.json"
    )
    assert fake_http.get_calls[0]["params"] == {"ref": "main"}


def test_get_feed_truncates_api_error_body_without_token_or_headers(client, fake_http):
    error_body = "x" * 600
    fake_http.get_response = FakeResponse(500, text=error_body)

    with pytest.raises(GitHubFeedError) as error:
        client.get_feed("docs/jingxuan/feed.json")

    assert str(error.value) == "GitHub Contents API 请求失败：" + "x" * 500
    assert "secret-token" not in str(error.value)
