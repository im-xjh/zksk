import json
import os
from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from exporter import FrequencyControlled, SessionExpired, fetch_account, latest_auth_key


ACCOUNT = {"name": "京宣", "fakeid": "fakeid-1"}
CUTOFF = 1_000
NEW_TS = 1_001
OLD_TS = 999


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []
        self.responses = []

    def queue(self, *responses):
        self.responses.extend(responses)

    def get(self, url, headers, params, timeout):
        self.calls.append(
            {"url": url, "headers": headers, "params": params, "timeout": timeout}
        )
        return FakeResponse(self.responses.pop(0))


@pytest.fixture
def fake_session():
    return FakeSession()


def article(title="new", ts=NEW_TS, link="https://example.test/article"):
    return {
        "title": title,
        "link": link,
        "digest": f"{title} summary",
        "aid": f"aid-{title}",
        "publish_time": ts,
    }


def page_with(*articles, ret=0, serialized=False):
    publish_page = {
        "publish_list": [{"publish_info": {"appmsgex": list(articles)}}]
    }
    return {
        "base_resp": {"ret": ret},
        "publish_page": json.dumps(publish_page) if serialized else publish_page,
    }


def test_fetch_account_initial_paginates_until_old_article(fake_session):
    fake_session.queue(page_with(article(ts=NEW_TS)), page_with(article(ts=OLD_TS)))

    result = fetch_account(
        fake_session,
        "http://exporter:3000",
        "auth",
        ACCOUNT,
        cutoff_ts=CUTOFF,
        initial=True,
        max_pages=10,
    )

    assert [item.title for item in result] == ["new"]
    assert [call["params"]["begin"] for call in fake_session.calls] == [0, 1]
    assert fake_session.calls[0] == {
        "url": "http://exporter:3000/api/web/mp/appmsgpublish",
        "headers": {"X-Auth-Key": "auth"},
        "params": {"id": "fakeid-1", "begin": 0, "size": 20},
        "timeout": 30,
    }


def test_fetch_account_regular_reads_only_first_page(fake_session):
    fake_session.queue(page_with(article(ts=NEW_TS), serialized=True))

    fetch_account(
        fake_session,
        "http://exporter:3000",
        "auth",
        ACCOUNT,
        cutoff_ts=CUTOFF,
        initial=False,
    )

    assert len(fake_session.calls) == 1


def test_fetch_account_raises_when_exporter_session_has_expired(fake_session):
    fake_session.queue(page_with(ret=200003))

    with pytest.raises(SessionExpired):
        fetch_account(
            fake_session,
            "http://exporter:3000",
            "auth",
            ACCOUNT,
            cutoff_ts=CUTOFF,
            initial=False,
        )


def test_fetch_account_retries_frequency_control_then_succeeds(fake_session):
    fake_session.queue(page_with(ret=200013), page_with(article(ts=NEW_TS)))
    waits = []

    result = fetch_account(
        fake_session,
        "http://exporter:3000",
        "auth",
        ACCOUNT,
        cutoff_ts=CUTOFF,
        initial=False,
        sleep=waits.append,
    )

    assert [item.title for item in result] == ["new"]
    assert waits == [5]
    assert len(fake_session.calls) == 2


def test_fetch_account_ignores_article_without_link(fake_session):
    fake_session.queue(page_with(article(link=""), article(title="kept", link="https://example.test/kept")))

    result = fetch_account(
        fake_session,
        "http://exporter:3000",
        "auth",
        ACCOUNT,
        cutoff_ts=CUTOFF,
        initial=False,
    )

    assert [item.title for item in result] == ["kept"]


def test_latest_auth_key_uses_newest_filename_without_reading_contents(tmp_path, monkeypatch):
    old_cookie = tmp_path / "old-auth-key"
    newest_cookie = tmp_path / "new-auth-key"
    old_cookie.write_text("old contents", encoding="utf-8")
    newest_cookie.write_text("new contents", encoding="utf-8")
    os.utime(old_cookie, (1, 1))
    os.utime(newest_cookie, (2, 2))

    def fail_if_read(*args, **kwargs):
        raise AssertionError("cookie contents must not be read")

    monkeypatch.setattr(Path, "read_text", fail_if_read)

    assert latest_auth_key(tmp_path) == "new-auth-key"


def test_fetch_account_raises_after_all_frequency_control_retries(fake_session):
    fake_session.queue(*(page_with(ret=200013) for _ in range(5)))
    waits = []

    with pytest.raises(FrequencyControlled):
        fetch_account(
            fake_session,
            "http://exporter:3000",
            "auth",
            ACCOUNT,
            cutoff_ts=CUTOFF,
            initial=False,
            sleep=waits.append,
        )

    assert waits == [5, 10, 20, 40]
