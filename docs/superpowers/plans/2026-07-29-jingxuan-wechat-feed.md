# 京宣参阅消息公众号采集与网页实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 复用腾讯云现有 `wechat-article-exporter`，每 10 分钟将指定公众号最近 10 天的文章写入 `im-xjh/zksk`，并通过 GitHub Pages 提供倒序文章列表。

**Architecture:** 在 `zksk` 中新增独立 Python 采集器、Docker 部署配置和原生静态网页。采集器通过现有 exporter 的 Docker 网络查询文章，以服务器 SQLite 去重，通过 GitHub Contents API 更新 `docs/jingxuan/feed.json`；GitHub Pages 从 `main:/docs` 发布网页。

**Tech Stack:** Python 3.12、requests、SQLite、pytest、Docker Compose、原生 HTML/CSS/JavaScript、GitHub REST API、GitHub Pages。

## Global Constraints

- 首次运行只回填最近 10 天，后续也只发布最近 10 天。
- 每 10 分钟运行一轮；公众号请求之间默认间隔 15 秒。
- 只有文章集合或展示字段变化时才更新 `feed.json`。
- JSON 是唯一正式采集结果；不输出 CSV。
- 网页只展示数据和原文链接，不保存任何交互状态。
- 不抓正文，不调用大模型，不接入 Cubox、Notion 或 Telegram。
- 不修改现有 `wechat-cubox-sync`、全文抓取和日报逻辑。
- 微信登录密钥与 GitHub Token 只保存在服务器，禁止进入仓库、JSON、网页和日志。
- 当前仓库中的 Markdown 文件使用 UTF-8 BOM。
- Python 依赖安装到项目 `.venv`，使用 `uv`，不污染系统 Python。
- 首次真实同步前必须取得用户提供的公众号清单；不得从现有 107 个账号中猜测目标账号。

---

## File Map

**Create**

- `京宣参阅消息/公众号采集/accounts.json`：用户确认的公众号名称和 `fakeid`。
- `京宣参阅消息/公众号采集/collector.py`：入口、调度和一轮任务编排。
- `京宣参阅消息/公众号采集/models.py`：文章规范化、10 天过滤、排序和 feed 生成。
- `京宣参阅消息/公众号采集/exporter.py`：auth-key 发现、exporter 请求、分页和频控退避。
- `京宣参阅消息/公众号采集/state.py`：SQLite 表结构、文章 upsert、现有任务避让。
- `京宣参阅消息/公众号采集/github_feed.py`：GitHub Contents API 读取和条件更新。
- `京宣参阅消息/公众号采集/config.py`：环境变量解析和校验。
- `京宣参阅消息/公众号采集/requirements.txt`：运行依赖。
- `京宣参阅消息/公众号采集/requirements-dev.txt`：测试依赖。
- `京宣参阅消息/公众号采集/Dockerfile`：采集器镜像。
- `京宣参阅消息/公众号采集/compose.yml`：独立 Compose 项目，接入 exporter 外部网络。
- `京宣参阅消息/公众号采集/.env.example`：非敏感变量示例。
- `京宣参阅消息/公众号采集/tests/`：Python 单元和集成测试。
- `docs/.nojekyll`：禁用 Jekyll 转换。
- `docs/jingxuan/index.html`：页面结构。
- `docs/jingxuan/app.js`：读取和渲染 feed。
- `docs/jingxuan/style.css`：桌面与移动端样式。
- `docs/jingxuan/feed.json`：首次部署前的空 feed。
- `docs/jingxuan/tests/app.test.mjs`：浏览器无关的前端格式化测试。

**Modify**

- `京宣参阅消息/公众号采集任务进度.md`：实现完成后更新架构、运行状态、网址和运维方法。
- `.gitignore`：如现有规则未覆盖，再加入采集器 `.venv/`、测试缓存和本地状态文件；只增加缺失规则。

---

### Task 1: 文章模型与最近 10 天 Feed

**Files:**

- Create: `京宣参阅消息/公众号采集/models.py`
- Create: `京宣参阅消息/公众号采集/tests/test_models.py`
- Create: `京宣参阅消息/公众号采集/requirements-dev.txt`
- Modify: `.gitignore`

**Interfaces:**

- Produces: `normalize_article(raw: dict, account: dict, tz: ZoneInfo) -> Article | None`
- Produces: `build_feed(rows: Iterable[Mapping], now: datetime, window_days: int = 10) -> dict`
- `Article` fields: `url`, `title`, `summary`, `account_name`, `fakeid`, `aid`, `published_at`, `publish_ts`

- [ ] **Step 1: 建立项目虚拟环境和测试依赖**

Append these missing repository-local runtime rules to `.gitignore`:

```gitignore
.venv/
.pytest_cache/
京宣参阅消息/公众号采集/state/
```

Run:

```bash
cd /Users/jhx/Documents/Code/zksk
uv venv /Users/jhx/Documents/Code/zksk/.venv
uv pip install --python /Users/jhx/Documents/Code/zksk/.venv/bin/python pytest requests
```

Create `京宣参阅消息/公众号采集/requirements-dev.txt`:

```text
-r requirements.txt
pytest==8.4.1
```

- [ ] **Step 2: 写规范化、时间窗口、去重和倒序测试**

Create tests covering these exact cases:

```python
def test_build_feed_keeps_exactly_last_ten_days():
    now = datetime(2026, 7, 29, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    rows = [
        article_row("inside", now - timedelta(days=9, hours=23)),
        article_row("boundary", now - timedelta(days=10)),
        article_row("outside", now - timedelta(days=10, seconds=1)),
    ]
    feed = build_feed(rows, now)
    assert [item["title"] for item in feed["articles"]] == ["inside", "boundary"]


def test_build_feed_deduplicates_url_and_sorts_newest_first():
    now = datetime(2026, 7, 29, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    rows = [
        article_row("older", now - timedelta(hours=2), url="https://example/1"),
        article_row("newer", now - timedelta(hours=1), url="https://example/2"),
        article_row("duplicate", now - timedelta(hours=3), url="https://example/2"),
    ]
    feed = build_feed(rows, now)
    assert [item["title"] for item in feed["articles"]] == ["newer", "older"]
    assert feed["article_count"] == 2
```

Also assert that `feed["articles"][0]` contains only `id`, `account_name`, `title`, `summary`, `published_at`, and `url`; `fakeid` and `aid` must not appear.

- [ ] **Step 3: 运行测试并确认失败**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests/test_models.py -v
```

Expected: FAIL because `models.py` and its interfaces do not exist.

- [ ] **Step 4: 实现最小文章模型和 feed 构造**

Use a frozen dataclass and deterministic URL hash:

```python
@dataclass(frozen=True)
class Article:
    url: str
    title: str
    summary: str
    account_name: str
    fakeid: str
    aid: str
    published_at: str
    publish_ts: int


def public_article(article: Article) -> dict:
    return {
        "id": hashlib.sha256(article.url.encode("utf-8")).hexdigest()[:16],
        "account_name": article.account_name,
        "title": article.title,
        "summary": article.summary,
        "published_at": article.published_at,
        "url": article.url,
    }
```

`build_feed` uses闭区间 `publish_ts >= int((now - timedelta(days=10)).timestamp())`，按 `(publish_ts, url)` 降序排列并按 URL 去重。`generated_at` 使用北京时间 ISO 8601。

- [ ] **Step 5: 运行模型测试**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests/test_models.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: 提交**

```bash
git add -- \
  '.gitignore' \
  '京宣参阅消息/公众号采集/models.py' \
  '京宣参阅消息/公众号采集/tests/test_models.py' \
  '京宣参阅消息/公众号采集/requirements-dev.txt'
git commit -m '实现公众号文章时间窗口模型'
```

---

### Task 2: Exporter 查询、首次分页和频控

**Files:**

- Create: `京宣参阅消息/公众号采集/exporter.py`
- Create: `京宣参阅消息/公众号采集/tests/test_exporter.py`
- Create: `京宣参阅消息/公众号采集/requirements.txt`

**Interfaces:**

- Consumes: `models.normalize_article`
- Produces: `latest_auth_key(cookie_dir: Path) -> str`
- Produces: `fetch_account(session, base_url: str, auth_key: str, account: dict, cutoff_ts: int, initial: bool, max_pages: int = 10) -> list[Article]`
- Produces: `SessionExpired` and `FrequencyControlled` exceptions

- [ ] **Step 1: 写 exporter 响应解析测试**

Fixtures must model `publish_page` as either a JSON object or JSON string and include `publish_list[*].publish_info.appmsgex`. Test:

```python
def test_fetch_account_initial_paginates_until_old_article(fake_session):
    fake_session.queue(page_with(article(ts=NEW_TS)), page_with(article(ts=OLD_TS)))
    result = fetch_account(
        fake_session, "http://exporter:3000", "auth", ACCOUNT,
        cutoff_ts=CUTOFF, initial=True, max_pages=10,
    )
    assert [item.title for item in result] == ["new"]
    assert [call["params"]["begin"] for call in fake_session.calls] == [0, 1]


def test_fetch_account_regular_reads_only_first_page(fake_session):
    fake_session.queue(page_with(article(ts=NEW_TS)))
    fetch_account(
        fake_session, "http://exporter:3000", "auth", ACCOUNT,
        cutoff_ts=CUTOFF, initial=False,
    )
    assert len(fake_session.calls) == 1
```

Also test:

- `base_resp.ret == 200003` raises `SessionExpired`.
- `base_resp.ret == 200013` retries with injected sleep and then succeeds.
- Missing article link is ignored.
- `latest_auth_key` selects the newest cookie filename without reading cookie contents.

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests/test_exporter.py -v
```

Expected: FAIL because `exporter.py` does not exist.

- [ ] **Step 3: 实现 exporter 客户端**

Request contract:

```python
response = session.get(
    f"{base_url}/api/web/mp/appmsgpublish",
    headers={"X-Auth-Key": auth_key},
    params={"id": account["fakeid"], "begin": begin, "size": 20},
    timeout=30,
)
```

Use retry waits `5, 10, 20, 40` seconds for `200013`, with `sleep` injected into `fetch_account` for tests. Raise on any nonzero `ret` after retry. First run paginates; regular runs stop after one page.

Create `requirements.txt`:

```text
requests==2.32.4
```

- [ ] **Step 4: 运行 exporter 测试**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests/test_exporter.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: 提交**

```bash
git add -- \
  '京宣参阅消息/公众号采集/exporter.py' \
  '京宣参阅消息/公众号采集/tests/test_exporter.py' \
  '京宣参阅消息/公众号采集/requirements.txt'
git commit -m '实现微信公众号列表查询'
```

---

### Task 3: SQLite 状态与现有任务避让

**Files:**

- Create: `京宣参阅消息/公众号采集/state.py`
- Create: `京宣参阅消息/公众号采集/tests/test_state.py`

**Interfaces:**

- Consumes: `models.Article`
- Produces: `open_state(path: Path) -> sqlite3.Connection`
- Produces: `upsert_articles(conn, articles: Iterable[Article], seen_at: str) -> tuple[int, int]`
- Produces: `recent_rows(conn, cutoff_ts: int) -> list[sqlite3.Row]`
- Produces: `existing_sync_active(db_path: Path, now: datetime) -> bool`

- [ ] **Step 1: 写 SQLite 测试**

Tests:

```python
def test_upsert_articles_is_idempotent(tmp_path):
    conn = open_state(tmp_path / "state.sqlite3")
    article = make_article(url="https://example/1")
    assert upsert_articles(conn, [article], NOW_ISO) == (1, 0)
    assert upsert_articles(conn, [article], NOW_ISO) == (0, 1)
    assert len(recent_rows(conn, 0)) == 1


def test_existing_sync_active_only_for_recent_unfinished_run(tmp_path):
    db = build_existing_runs_db(
        tmp_path / "wechat_articles.sqlite3",
        started_at="2026-07-29T01:00:00Z",
        finished_at=None,
    )
    now = datetime(2026, 7, 29, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert existing_sync_active(db, now) is True
```

Also test that an unfinished run older than two hours and a finished run both return `False`; a missing existing DB returns `False`.

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests/test_state.py -v
```

Expected: FAIL because `state.py` does not exist.

- [ ] **Step 3: 实现数据库**

Create one `articles` table with URL primary key and all `Article` fields plus `first_seen_at` and `last_seen_at`. Use `INSERT ... ON CONFLICT(url) DO UPDATE` for mutable display fields. Open the existing sync DB using:

```python
sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
```

Query `runs` for the newest row where `finished_at IS NULL`; compare `started_at` with `now - timedelta(hours=2)`.

- [ ] **Step 4: 运行状态测试**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests/test_state.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: 提交**

```bash
git add -- \
  '京宣参阅消息/公众号采集/state.py' \
  '京宣参阅消息/公众号采集/tests/test_state.py'
git commit -m '增加公众号采集去重状态'
```

---

### Task 4: GitHub Feed 条件发布

**Files:**

- Create: `京宣参阅消息/公众号采集/github_feed.py`
- Create: `京宣参阅消息/公众号采集/tests/test_github_feed.py`

**Interfaces:**

- Produces: `GitHubFeedClient(token: str, repo: str, branch: str = "main", session: requests.Session | None = None)`
- Produces: `GitHubFeedClient.get_feed(path: str) -> tuple[dict | None, str | None]`
- Produces: `GitHubFeedClient.publish_if_changed(path: str, feed: dict) -> PublishResult`
- `PublishResult` fields: `changed: bool`, `commit_sha: str | None`

- [ ] **Step 1: 写无变化跳过和更新测试**

```python
def test_publish_if_changed_skips_same_articles(client, fake_http):
    remote = feed(["a"], generated_at="old")
    fake_http.respond_get(remote, sha="blob-sha")
    result = client.publish_if_changed("docs/jingxuan/feed.json", feed(["a"], generated_at="new"))
    assert result.changed is False
    assert fake_http.put_calls == []


def test_publish_if_changed_puts_changed_feed_with_sha(client, fake_http):
    fake_http.respond_get(feed(["a"]), sha="blob-sha")
    fake_http.respond_put(commit_sha="commit-sha")
    result = client.publish_if_changed("docs/jingxuan/feed.json", feed(["b"]))
    assert result == PublishResult(changed=True, commit_sha="commit-sha")
    assert fake_http.put_calls[0]["json"]["sha"] == "blob-sha"
```

Also test initial `404` creation, UTF-8 JSON encoding, URL quoting for repository paths, and API error bodies truncated to 500 characters without headers or token.

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests/test_github_feed.py -v
```

Expected: FAIL because `github_feed.py` does not exist.

- [ ] **Step 3: 实现 GitHub Contents API 客户端**

Use:

```text
GET /repos/im-xjh/zksk/contents/docs/jingxuan/feed.json?ref=main
PUT /repos/im-xjh/zksk/contents/docs/jingxuan/feed.json
```

Compare only `window_days` and `articles`; ignore `generated_at` and `article_count` when deciding whether content changed. On change, serialize with `ensure_ascii=False`, `indent=2`, trailing newline, then base64 encode. Commit message: `更新京宣公众号文章列表`。

- [ ] **Step 4: 运行 GitHub 发布测试**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests/test_github_feed.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: 提交**

```bash
git add -- \
  '京宣参阅消息/公众号采集/github_feed.py' \
  '京宣参阅消息/公众号采集/tests/test_github_feed.py'
git commit -m '实现公众号Feed条件发布'
```

---

### Task 5: 一轮采集、定时调度与配置

**Files:**

- Create: `京宣参阅消息/公众号采集/config.py`
- Create: `京宣参阅消息/公众号采集/collector.py`
- Create: `京宣参阅消息/公众号采集/tests/test_collector.py`
- Create: `京宣参阅消息/公众号采集/.env.example`
- Create: `京宣参阅消息/公众号采集/accounts.json`

**Interfaces:**

- Consumes: Tasks 1–4 interfaces
- Produces: `Config.load() -> Config`
- Produces: `Dependencies` dataclass containing exporter session, state factory, GitHub client factory, clock and sleep callables
- Produces: `run_once(config: Config, initial: bool = False, deps: Dependencies | None = None) -> RunReport`
- Produces: CLI commands `python collector.py validate-accounts`, `python collector.py once [--initial]` and `python collector.py run`

- [ ] **Step 1: 写编排测试**

Use injected exporter client, state connection and GitHub client. Test:

```python
def test_run_once_publishes_recent_articles_in_account_order_independent_way(deps, config):
    deps.exporter.return_by_fakeid = {
        "a": [make_article("new", hours_ago=1)],
        "b": [make_article("old", days_ago=11)],
    }
    report = run_once(config, initial=True, deps=deps)
    assert report.accounts_ok == 2
    assert report.published is True
    assert [x["title"] for x in deps.github.last_feed["articles"]] == ["new"]


def test_run_once_skips_during_existing_daily_sync(deps, config):
    deps.existing_sync_active = True
    report = run_once(config, deps=deps)
    assert report.skipped_reason == "existing_sync_active"
    assert deps.exporter.calls == []
```

Also test:

- Empty `accounts.json` fails before network access.
- Duplicate or missing `fakeid` fails configuration validation.
- `SessionExpired` aborts publication and returns nonzero CLI status.
- One ordinary account error is reported while other accounts continue.
- Complete account failure with an empty state does not publish an empty feed.
- Scheduler waits `max(1, 600 - elapsed_seconds)` between run starts.

- [ ] **Step 2: 运行编排测试并确认失败**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests/test_collector.py -v
```

Expected: FAIL because `config.py` and `collector.py` do not exist.

- [ ] **Step 3: 实现配置和 CLI**

Required environment variables:

```text
GITHUB_TOKEN
```

Defaults:

```text
EXPORTER_BASE_URL=http://wechat-article-exporter:3000
AUTH_COOKIE_DIR=/exporter-kv-cookie
ACCOUNTS_FILE=/app/accounts.json
STATE_DB=/state/jingxuan_articles.sqlite3
EXISTING_SYNC_DB=/existing-sync-state/wechat_articles.sqlite3
GITHUB_REPO=im-xjh/zksk
GITHUB_BRANCH=main
GITHUB_FEED_PATH=docs/jingxuan/feed.json
WINDOW_DAYS=10
INTERVAL_SECONDS=600
ACCOUNT_DELAY_SECONDS=15
TZ=Asia/Shanghai
```

`run_once` logs only counts, account names, error classes and commit SHA; never log request headers, auth-key filename or environment values.

Create `.env.example` with the defaults and an empty `GITHUB_TOKEN=`. Create `accounts.json` as an empty manifest:

```json
{
  "version": 1,
  "accounts": []
}
```

The empty manifest is intentionally non-runnable until the user provides the real list.

- [ ] **Step 4: 运行全部 Python 测试**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests -v
```

Expected: all tests PASS.

- [ ] **Step 5: 提交**

```bash
git add -- \
  '京宣参阅消息/公众号采集/config.py' \
  '京宣参阅消息/公众号采集/collector.py' \
  '京宣参阅消息/公众号采集/tests/test_collector.py' \
  '京宣参阅消息/公众号采集/.env.example' \
  '京宣参阅消息/公众号采集/accounts.json'
git commit -m '完成公众号采集任务编排'
```

---

### Task 6: 纯静态 GitHub Pages 阅读页

**Files:**

- Create: `docs/.nojekyll`
- Create: `docs/jingxuan/index.html`
- Create: `docs/jingxuan/app.js`
- Create: `docs/jingxuan/style.css`
- Create: `docs/jingxuan/feed.json`
- Create: `docs/jingxuan/tests/app.test.mjs`

**Interfaces:**

- Consumes: `docs/jingxuan/feed.json` Task 1 schema
- Produces: `formatPublishedAt(iso: string) -> string`
- Produces: `renderArticle(article: object) -> string`

- [ ] **Step 1: 写前端格式化测试**

`app.js` must expose pure functions through `module.exports` when `typeof module !== "undefined"` and start browser loading only when `typeof document !== "undefined"`。

Test:

```javascript
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { formatPublishedAt, renderArticle } = require("../app.js");

test("formatPublishedAt renders Beijing month day and time", () => {
  assert.equal(formatPublishedAt("2026-07-29T09:30:00+08:00"), "07月29日 09:30");
});

test("renderArticle escapes text and keeps a safe article URL", () => {
  const html = renderArticle({
    account_name: "<公众号>",
    title: "<script>alert(1)</script>",
    summary: "摘要",
    published_at: "2026-07-29T09:30:00+08:00",
    url: "https://mp.weixin.qq.com/s/example"
  });
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /target="_blank"/);
  assert.match(html, /rel="noopener noreferrer"/);
});
```

- [ ] **Step 2: 运行前端测试并确认失败**

Run:

```bash
node --test /Users/jhx/Documents/Code/zksk/docs/jingxuan/tests/app.test.mjs
```

Expected: FAIL because frontend files do not exist.

- [ ] **Step 3: 创建空 feed 和页面**

Initial `feed.json`:

```json
{
  "version": 1,
  "generated_at": null,
  "window_days": 10,
  "article_count": 0,
  "articles": []
}
```

Page requirements:

- `<title>` and H1 use“京宣公众号最新文章”。
- Header shows update time and“最近 10 天共 N 篇”。
- Each article is a semantic `<article>` with account/time metadata, linked title and optional summary.
- Loading, empty and error states are visible text.
- No forms, buttons, cookies, local storage or analytics.
- `fetch("./feed.json", {cache: "no-store"})` prevents the browser from intentionally reusing a stale local response.

CSS requirements:

- Content width `min(920px, calc(100% - 32px))`。
- Body font uses system Chinese sans-serif stack.
- Article rows use a single column at all widths.
- Long titles and URLs wrap; no horizontal overflow at 375 px.
- Visited article links may use a distinct muted color only through browser-native `:visited`。

- [ ] **Step 4: 运行前端测试**

Run:

```bash
node --test /Users/jhx/Documents/Code/zksk/docs/jingxuan/tests/app.test.mjs
```

Expected: all tests PASS.

- [ ] **Step 5: 本地浏览器验证**

Run:

```bash
cd /Users/jhx/Documents/Code/zksk/docs
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m http.server 8765
```

Open `http://127.0.0.1:8765/jingxuan/` and verify:

- Empty state renders without console errors.
- Replace the local feed with three fixture articles and confirm newest-first order.
- Each title opens its exact `mp.weixin.qq.com` URL in a new tab.
- At 1440 px and 375 px widths the page has no horizontal overflow.
- A malformed feed shows the error state and preserves the page shell.

Stop the local server after verification.

- [ ] **Step 6: 提交**

```bash
git add -- \
  'docs/.nojekyll' \
  'docs/jingxuan/index.html' \
  'docs/jingxuan/app.js' \
  'docs/jingxuan/style.css' \
  'docs/jingxuan/feed.json' \
  'docs/jingxuan/tests/app.test.mjs'
git commit -m '增加京宣公众号阅读页面'
```

---

### Task 7: Docker 部署配置

**Files:**

- Create: `京宣参阅消息/公众号采集/Dockerfile`
- Create: `京宣参阅消息/公众号采集/compose.yml`
- Create: `京宣参阅消息/公众号采集/tests/test_deploy_config.py`

**Interfaces:**

- Consumes: `collector.py run`
- Produces: Docker service `jingxuan-wechat-collector`

- [ ] **Step 1: 写部署配置测试**

The test parses files as text and asserts:

```python
def test_compose_uses_existing_exporter_network_and_read_only_mounts():
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "wechat-article-exporter_default" in compose
    assert "/opt/wechat-article-exporter/data/kv/cookie:/exporter-kv-cookie:ro" in compose
    assert "/opt/wechat-article-exporter/sync-state:/existing-sync-state:ro" in compose
    assert "GITHUB_TOKEN: ${GITHUB_TOKEN:?GITHUB_TOKEN is required}" in compose
```

Also assert Dockerfile uses Python 3.12 slim, installs only `requirements.txt`, copies focused source files, creates a non-root user and runs `python /app/collector.py run`.

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests/test_deploy_config.py -v
```

Expected: FAIL because Docker files do not exist.

- [ ] **Step 3: 创建独立 Compose 项目**

Compose service requirements:

```yaml
services:
  jingxuan-wechat-collector:
    build: .
    image: jingxuan-wechat-collector:local
    container_name: jingxuan-wechat-collector
    restart: unless-stopped
    environment:
      GITHUB_TOKEN: ${GITHUB_TOKEN:?GITHUB_TOKEN is required}
      TZ: Asia/Shanghai
    volumes:
      - /opt/wechat-article-exporter/data/kv/cookie:/exporter-kv-cookie:ro
      - /opt/wechat-article-exporter/sync-state:/existing-sync-state:ro
      - ./state:/state
      - ./accounts.json:/app/accounts.json:ro
    networks:
      - exporter

networks:
  exporter:
    external: true
    name: wechat-article-exporter_default
```

Run container as UID/GID `10001`，which can write `/state`; initialize server `state/` ownership before starting.

- [ ] **Step 4: 运行全部本地测试和镜像构建**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests -v
node --test /Users/jhx/Documents/Code/zksk/docs/jingxuan/tests/app.test.mjs
docker compose -f /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/compose.yml config
docker build -t jingxuan-wechat-collector:test \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集
```

Expected: tests PASS, Compose resolves, Docker build succeeds.

- [ ] **Step 5: 提交**

```bash
git add -- \
  '京宣参阅消息/公众号采集/Dockerfile' \
  '京宣参阅消息/公众号采集/compose.yml' \
  '京宣参阅消息/公众号采集/tests/test_deploy_config.py'
git commit -m '增加公众号采集容器配置'
```

---

### Task 8: 真实清单、服务器部署与首次 10 天同步

**Files:**

- Modify: `京宣参阅消息/公众号采集/accounts.json`
- Runtime target: `/opt/jingxuan-wechat-collector`

**Interfaces:**

- Requires: user-provided account nickname and `fakeid` list
- Produces: running `jingxuan-wechat-collector` and first `feed.json` commit

- [ ] **Step 1: 校验用户提供的公众号清单**

Convert only these fields:

```json
{
  "version": 1,
  "accounts": [
    {"nickname": "公众号名称", "fakeid": "公众号 fakeid"}
  ]
}
```

Run a validation command that prints counts and duplicate names/IDs but never prints secrets:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/collector.py validate-accounts
```

Expected: exact user-provided count, zero missing IDs, zero duplicate IDs.

- [ ] **Step 2: 提交清单**

```bash
git add -- '京宣参阅消息/公众号采集/accounts.json'
git commit -m '配置京宣监测公众号清单'
```

- [ ] **Step 3: 完整测试并先推送代码**

Run:

```bash
/Users/jhx/Documents/Code/zksk/.venv/bin/python -m pytest \
  /Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/tests -v
node --test /Users/jhx/Documents/Code/zksk/docs/jingxuan/tests/app.test.mjs
git status --short
git log --oneline origin/main..main
git push origin main
```

The site and initial empty `feed.json` must exist on remote `main` before the server publishes real data, preventing a later non-fast-forward push.

- [ ] **Step 4: 部署代码，不覆盖现有微信目录**

Run:

```bash
ssh TencentCloud '
  install -d -m 0750 /opt/jingxuan-wechat-collector
  install -d -o 10001 -g 10001 -m 0750 /opt/jingxuan-wechat-collector/state
'
rsync -av --delete \
  --exclude state \
  '/Users/jhx/Documents/Code/zksk/京宣参阅消息/公众号采集/' \
  TencentCloud:/opt/jingxuan-wechat-collector/
```

Verify exact target before and after rsync. Do not deploy into `/opt/wechat-article-exporter/sync-tool`。

- [ ] **Step 5: 构建并执行首次同步**

Use the existing server token for the first verification without printing it:

```bash
ssh TencentCloud '
  cd /opt/jingxuan-wechat-collector &&
  docker compose --env-file /opt/wechat-article-exporter/.env build &&
  docker compose --env-file /opt/wechat-article-exporter/.env run --rm \
    jingxuan-wechat-collector python /app/collector.py once --initial
'
```

Expected:

- Every configured account is attempted.
- No article older than 10 days appears in the run summary.
- GitHub receives one `feed.json` commit.
- Logs contain no auth-key or token.

- [ ] **Step 6: 检查首次 JSON**

Fetch `docs/jingxuan/feed.json` from GitHub and assert:

```text
window_days == 10
article_count == len(articles)
all published_at >= now - 10 days
URLs are unique
articles are newest-first
```

Manually sample at least five links across different accounts and confirm title/account/link alignment.

- [ ] **Step 7: 验证第二次运行幂等**

Run:

```bash
ssh TencentCloud '
  cd /opt/jingxuan-wechat-collector &&
  docker compose --env-file /opt/wechat-article-exporter/.env run --rm \
    jingxuan-wechat-collector python /app/collector.py once
'
```

Verify `published=false` with no new GitHub commit. Do not start the scheduler yet, so it cannot race with the remaining local progress-document commit.

---

### Task 9: 同步远端 Feed、启用 Pages 与上线验收

**Files:**

- Modify: `京宣参阅消息/公众号采集任务进度.md`

**Interfaces:**

- Produces: `https://im-xjh.github.io/zksk/jingxuan/`

- [ ] **Step 1: 将首次 Feed 提交同步回本地**

The initial collector run advanced remote `main`. Synchronize it before editing the progress document:

```bash
git status --short
git pull --ff-only origin main
git log -3 --oneline
```

- [ ] **Step 2: 更新进度文档并推送**

Record:

- Final architecture and file paths.
- Server container name and deployment directory.
- GitHub Pages target URL.
- First successful run time, account count and article count.
- Login-expiry recovery command.
- Container status/log/manual-run commands.
- Confirmed 10-day retention and 10-minute polling.

Do not include IP credentials, token, auth-key filename or cookie values.

Run:

```bash
git diff --check
git add -- '京宣参阅消息/公众号采集任务进度.md'
git commit -m '记录京宣公众号采集上线状态'
git push origin main
```

- [ ] **Step 3: 启用 Pages**

Configure repository Pages source as `main:/docs` through GitHub repository settings or the Pages REST API. Verify deployment reaches terminal status `built`.

- [ ] **Step 4: 启动定时容器**

Run:

```bash
ssh TencentCloud '
  cd /opt/jingxuan-wechat-collector &&
  docker compose --env-file /opt/wechat-article-exporter/.env up -d &&
  docker compose ps &&
  docker logs --tail=120 jingxuan-wechat-collector
'
```

Expected: service is `Up`, scheduler logs the next run interval, and no secret value appears.

- [ ] **Step 5: 浏览器端到端验证**

Open:

```text
https://im-xjh.github.io/zksk/jingxuan/
```

Verify:

- Page loads over HTTPS on desktop and a second device.
- Page count matches `feed.json.article_count`.
- First article matches the newest `published_at`.
- At least five sampled titles open the correct WeChat URLs.
- Refresh after a changed `feed.json` deployment shows the new article.
- There are no console errors or mixed-content requests.

- [ ] **Step 6: 最终运行状态验证**

Run:

```bash
git status --short
ssh TencentCloud 'docker ps --filter name=jingxuan-wechat-collector'
ssh TencentCloud 'docker logs --tail=120 jingxuan-wechat-collector'
```

Final acceptance requires a clean local worktree except pre-existing user files, the server container running, first 10-day data visible in GitHub, Pages live on two devices, and a second unchanged collection producing no commit.
