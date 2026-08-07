# 京宣公众号一天窗口激活实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将京宣公众号 Feed 的固定窗口从最近10天改为最近1天，导入用户提供的19个公众号，并在代码审查通过后完成腾讯云首次同步和10分钟常驻轮询。

**Architecture:** 保持现有采集器、SQLite、GitHub Contents API、GitHub Pages 和 Docker 部署结构不变。窗口仍是跨配置、模型、Feed 与网页的一致固定契约，仅把固定值改为1；公众号清单从 `/Users/jhx/Downloads/公众号.json` 中提取 `nickname` 与 `fakeid`，不保留导出器状态及文章缓存字段。

**Tech Stack:** Python 3.11/3.12、pytest、原生 JavaScript、Node.js test runner、Docker Compose、GitHub Pages。

## Global Constraints

- Feed 只包含当前北京时间向前24小时至当前时间的文章，边界采用闭区间。
- `window_days` 在配置、模型、静态 Feed 和网页校验中固定为整数1，其他值必须拒绝。
- 轮询间隔继续固定为600秒，公众号之间继续间隔15秒；首次同步每个公众号最多翻10页。
- 公众号清单严格为 `{"version": 1, "accounts": [...]}`，每项只保留非空 `nickname` 与 `fakeid`，保持源文件顺序，共19项，`fakeid` 不重复。
- 不修改文章字段、去重方式、GitHub 发布条件、Docker 网络、挂载、身份或安全日志规则。
- 不触碰主工作区现有的未跟踪文件。
- Markdown 保持 UTF-8 with BOM。

---

### Task 1: 一天窗口契约和正式公众号清单

**Files:**
- Modify: `京宣参阅消息/公众号采集/config.py`
- Modify: `京宣参阅消息/公众号采集/models.py`
- Modify: `京宣参阅消息/公众号采集/.env.example`
- Modify: `京宣参阅消息/公众号采集/accounts.json`
- Modify: `京宣参阅消息/公众号采集/tests/test_collector.py`
- Modify: `京宣参阅消息/公众号采集/tests/test_models.py`
- Modify: `京宣参阅消息/公众号采集/tests/test_github_feed.py`
- Modify: `docs/jingxuan/app.js`
- Modify: `docs/jingxuan/feed.json`
- Modify: `docs/jingxuan/tests/app.test.mjs`
- Modify: `京宣参阅消息/公众号采集任务进度.md`

**Interfaces:**
- Consumes: `/Users/jhx/Downloads/公众号.json`，其中 `accounts` 为19项，正式字段为 `nickname` 与 `fakeid`。
- Produces: `Config.window_days == 1`；`build_feed(..., window_days=1)`；`feed.json.window_days == 1`；网页只接受 `window_days === 1`；可通过 `validate-accounts` 的19项清单。

- [ ] **Step 1: 写出一天窗口的失败测试**

将 Python 测试改为手工构造以下边界：`now - timedelta(days=1)` 必须保留，`now - timedelta(days=1, seconds=1)` 必须排除；配置只接受字符串 `"1"` 并拒绝 `"10"`、`"0"` 和非整数；所有 Feed 测试样本使用 `"window_days": 1`。

将 Node 测试样本改为 `window_days: 1`；验证 `window_days = 10` 会抛出 `TypeError`。

- [ ] **Step 2: 运行测试并确认按预期失败**

Run:

```bash
京宣参阅消息/公众号采集/.venv/bin/python -m pytest \
  京宣参阅消息/公众号采集/tests/test_models.py \
  京宣参阅消息/公众号采集/tests/test_collector.py \
  京宣参阅消息/公众号采集/tests/test_github_feed.py -q

node --test docs/jingxuan/tests/app.test.mjs
```

Expected: Python 因生产配置和模型仍固定10天而失败；Node 因网页仍只接受10天而失败。

- [ ] **Step 3: 实现最小的一天窗口改动**

在 `config.py` 中将 `DEFAULTS["WINDOW_DAYS"]` 改为 `"1"`，只允许整数1，错误消息改为“`WINDOW_DAYS 必须为 1`”。在 `models.py` 中将 `build_feed` 默认值改为1。在 `app.js` 中只接受 `feed.window_days === 1`。

将 `.env.example` 与 `docs/jingxuan/feed.json` 的窗口改为1。

- [ ] **Step 4: 导入精简公众号清单**

读取 `/Users/jhx/Downloads/公众号.json` 的 `accounts`，按原顺序生成：

```json
{
  "version": 1,
  "accounts": [
    {
      "nickname": "源项 nickname",
      "fakeid": "源项 fakeid"
    }
  ]
}
```

输出必须恰有19项，每项恰有 `nickname`、`fakeid` 两个键，且 `fakeid` 唯一。不得复制 `articles`、`completed`、`count`、时间、头像或总数等字段。

- [ ] **Step 5: 更新实施记录**

把 `公众号采集任务进度.md` 中描述数据窗口的现行内容改为最近1天、向前24小时；保留“每10分钟”“最多10页”和退避等待中的数字10。增加2026年7月30日变更记录：收到19项清单，窗口由10天改为1天，等待首次同步和常驻运行验收。清单示例继续使用虚构名称，不写真实 `fakeid`。

- [ ] **Step 6: 运行完整验证**

Run:

```bash
京宣参阅消息/公众号采集/.venv/bin/python -m pytest \
  京宣参阅消息/公众号采集/tests -q
node --test docs/jingxuan/tests/app.test.mjs
京宣参阅消息/公众号采集/.venv/bin/python -m compileall -q \
  京宣参阅消息/公众号采集
GITHUB_TOKEN=verification-token docker compose \
  -f 京宣参阅消息/公众号采集/compose.yml config --quiet
git diff --check
```

Expected: Python 与 Node 全部通过，编译、Compose 和差异检查退出码均为0。

- [ ] **Step 7: 提交**

```bash
git add \
  京宣参阅消息/公众号采集 \
  京宣参阅消息/公众号采集任务进度.md \
  docs/jingxuan
git commit -m "启用京宣公众号一天采集窗口"
```

## 合并后部署验收

代码审查通过并合并、推送 `main` 后执行以下验收：

1. 将采集目录同步到腾讯云 `/opt/jingxuan-wechat-collector`，保留 `state`。
2. 运行 Compose 配置解析和镜像构建。
3. 在容器中运行 `validate-accounts`，必须显示19个账号。
4. 在常驻服务未启动的前提下运行 `once --initial`；若既有同步任务活跃导致跳过，等待其结束后重试。
5. 首次同步必须成功发布 `window_days == 1` 的 Feed，所有文章时间处于向前24小时闭区间，URL 唯一且倒序。
6. 等待 GitHub Pages 对 Feed 提交构建完成，公网网页和 `feed.json` 均返回 HTTP 200。
7. 执行 `docker compose up -d`，确认容器运行且无重启循环。
8. 观察至少一轮日志；再次执行无变化采集时不产生 Feed 提交。
