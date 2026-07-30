# Task 1 实施报告

## 结果

已将京宣公众号采集窗口固定为1天，并按源文件原顺序导入19项正式账号清单。公开 Feed 和网页均只接受 `window_days: 1`。

## TDD 红灯记录

命令：

```bash
京宣参阅消息/公众号采集/.venv/bin/python -m pytest \
  京宣参阅消息/公众号采集/tests/test_models.py \
  京宣参阅消息/公众号采集/tests/test_collector.py \
  京宣参阅消息/公众号采集/tests/test_github_feed.py -q
```

退出码：1。

失败原因：3项测试失败。旧的10天默认窗口错误保留了“向前1天1秒”的文章；配置仍接受字符串 `"10"` 并拒绝 `"1"`。

命令：

```bash
node --test docs/jingxuan/tests/app.test.mjs
```

退出码：1。

失败原因：2项测试失败。网页仍拒绝 `window_days: 1`，同时接受 `window_days: 10`。

## 绿灯记录

实现最小改动后重新运行上述目标测试。

- Python 目标测试：退出码0，45项通过。
- Node 目标测试：退出码0，10项通过。

## 全量验证

| 命令 | 结果 |
| --- | --- |
| `京宣参阅消息/公众号采集/.venv/bin/python -m pytest 京宣参阅消息/公众号采集/tests -q` | 退出码0，58项通过。 |
| `node --test docs/jingxuan/tests/app.test.mjs` | 退出码0，10项通过。 |
| `京宣参阅消息/公众号采集/.venv/bin/python -m compileall -q 京宣参阅消息/公众号采集` | 退出码0。 |
| `GITHUB_TOKEN=verification-token docker compose -f 京宣参阅消息/公众号采集/compose.yml config --quiet` | 退出码0。 |
| `git diff --check` | 退出码0。 |
| `GITHUB_TOKEN=verification-token ACCOUNTS_FILE="$PWD/京宣参阅消息/公众号采集/accounts.json" 京宣参阅消息/公众号采集/.venv/bin/python 京宣参阅消息/公众号采集/collector.py validate-accounts` | 退出码0，显示19个账号。 |

## 数据校验与自审

- 源文件的 `accounts` 有19项，导入后仍为19项，顺序未改变。
- 每项严格只有 `nickname`、`fakeid` 两个字段；未导入文章、完成状态、计数、时间、头像或汇总字段。
- `fakeid` 全部非空且唯一；本报告未打印任何具体 `fakeid`。
- 模型边界测试覆盖向前24小时闭区间：恰好1天前保留，早1秒排除。
- 配置测试覆盖只接受字符串 `"1"`，拒绝 `"10"`、`"0"` 和非整数值。
- 网页测试覆盖只接受 `window_days: 1`，并拒绝 `window_days: 10`。
- 已复核任务范围：未修改计划文件或 ledger。

## 关注项

首次同步、GitHub Pages 公网检查和常驻容器验收属于合并推送后的服务器部署步骤，当前工作树尚未执行。

## Fix round 1 审查修复

### 红灯

命令：

```bash
京宣参阅消息/公众号采集/.venv/bin/python -m pytest \
  京宣参阅消息/公众号采集/tests/test_models.py \
  京宣参阅消息/公众号采集/tests/test_collector.py -q
```

退出码：1。

预期失败：`build_feed(..., window_days=10)` 未抛出异常；配置仍接受 `"01"`、`"+1"` 和 `" 1"`。

### 绿灯与全量验证

覆盖测试命令：

```bash
京宣参阅消息/公众号采集/.venv/bin/python -m pytest \
  京宣参阅消息/公众号采集/tests/test_models.py \
  京宣参阅消息/公众号采集/tests/test_collector.py -q
```

结果：退出码0，40项通过。

| 命令 | 结果 |
| --- | --- |
| `京宣参阅消息/公众号采集/.venv/bin/python -m pytest 京宣参阅消息/公众号采集/tests -q` | 退出码0，62项通过。 |
| `node --test docs/jingxuan/tests/app.test.mjs` | 退出码0，10项通过。 |
| `京宣参阅消息/公众号采集/.venv/bin/python -m compileall -q 京宣参阅消息/公众号采集` | 退出码0。 |
| `GITHUB_TOKEN=verification-token docker compose -f 京宣参阅消息/公众号采集/compose.yml config --quiet` | 退出码0。 |
| `git diff --check` | 退出码0。 |

### 自审

- `build_feed` 在生成 Feed 前拒绝任何不等于1的显式窗口参数，避免生成10天 Feed。
- `WINDOW_DAYS` 只接受原始字符串精确为 `"1"`，因此拒绝前导零、符号和空白；固定错误消息不包含输入值。
- 为前导空格样本将原有“输入值不在错误消息中”的断言改为固定安全消息比较，避免要求中的 `" 1"` 被消息末尾的“为 1”误判为回显。

## Fix round 2 审查修复

### 红灯

命令：

```bash
京宣参阅消息/公众号采集/.venv/bin/python -m pytest \
  京宣参阅消息/公众号采集/tests/test_models.py -q
```

退出码：1。

预期失败：新增参数化测试确认 `True` 与 `1.0` 被 Python 的相等比较误认为1，`build_feed` 未抛出异常。

### 绿灯与全量验证

覆盖测试命令：

```bash
京宣参阅消息/公众号采集/.venv/bin/python -m pytest \
  京宣参阅消息/公众号采集/tests/test_models.py -q
```

结果：退出码0，6项通过。

| 命令 | 结果 |
| --- | --- |
| `京宣参阅消息/公众号采集/.venv/bin/python -m pytest 京宣参阅消息/公众号采集/tests -q` | 退出码0，64项通过。 |
| `node --test docs/jingxuan/tests/app.test.mjs` | 退出码0，10项通过。 |
| `京宣参阅消息/公众号采集/.venv/bin/python -m compileall -q 京宣参阅消息/公众号采集` | 退出码0。 |
| `GITHUB_TOKEN=verification-token docker compose -f 京宣参阅消息/公众号采集/compose.yml config --quiet` | 退出码0。 |
| `git diff --check` | 退出码0。 |

### 自审

- `build_feed` 仅接受精确 `int` 类型且值为1的窗口参数，`bool` 与 `float` 均会以固定安全错误拒绝。
