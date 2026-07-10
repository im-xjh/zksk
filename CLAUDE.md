# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作时提供指导。

## 项目概述

这是一个中文舆情报告工作空间。核心工作流为：以 Markdown 撰写报告 → 转换为格式化 `.docx` 文档报送。

## 关键转换工具

两套独立的 Markdown 转 DOCX 流水线，分别服务于不同类型的报告：

### 1. 根目录通用转换器（`md_to_word_report.py`）

适用于"简报"类报告。支持两种正文字号预设：
- `small2`（小二/18pt）—— 标题二号，一级标题小二，正文小二
- `3`（三号/16pt）—— 标题小二，一级标题小二，正文三号

二级及以上标题使用正文字号并加粗。用法：

```bash
# 通过启动器（Windows 推荐）：
md_to_word_report.cmd input.md [-o output.docx] [--body-size small2|3] [--filename-title]

# 直接调用：
python md_to_word_report.py input.md [-o output.docx] [--body-size small2|3]
```

### 2. 海淀周报转换器（`海淀周报/md转Word工具包/convert.py`）

一套更严格的转换器，用于海淀区意识形态周报。强制精确排版：
- A4 页面，页边距：上下 2.54 cm，左右 3.18 cm
- 标题：方正大标宋简体 二号，居中，后跟一行空行
- 一级标题：黑体 三号，缩进 2 字符
- 正文：仿宋_GB2312 三号，两端对齐，首行缩进 2 字符，固定行距 28 磅
- 表格：微软雅黑 10pt 正文 / 11pt 加粗表头，固定列宽
- 页脚自动添加页码

**严格解析规则：** 仅支持 `#`（一级标题）。文本若看起来像章节标题（如"一、……"）但未使用 `#` 将报错。图片必须独占一行。网络图片将被拒绝。

```bash
# GUI 文件选择器（双击 .cmd）：
一键转Word.cmd

# 命令行：
python convert.py INPUT.md [-o OUTPUT.docx] [--force] [--no-open]

# 依赖项（首次运行时由 .cmd 自动安装）：
pip install python-docx Pillow
```

### 3. 境外敏感信息专报转换器（`摘编/境外敏感信息专报md转Word工具包/convert.py`）

用于"境外敏感信息专报"，将 Markdown 草稿转换为带固定封面、目录和正文样式的 Word 文档。

- 通过模板（`templates/境外敏感信息专报模板.docx`）填充 `{{TOC}}` 和 `{{BODY}}` 占位符
- 支持三种目录页码模式：`manual`（手动填写）、`blank`（待核）、`estimate`（估算）
- 正文：仿宋_GB2312 三号（16pt），固定行距 28 磅，首行缩进约 2 字符
- 不支持图片、表格、三级及以上标题

```bash
# GUI 文件选择器：
一键转Word.cmd

# 命令行：
python convert.py INPUT.md [-o OUTPUT.docx] [--force] [--no-open] [--toc-pages manual|blank|estimate]
```

## 项目规范

- **编码：** 所有 Markdown 文件使用 UTF-8 with BOM（`utf-8-sig`）。转换器以 UTF-8 读写。
- **字体：** 需要 Windows 字体 —— 方正小标宋简体 / 方正大标宋简体、黑体、仿宋_GB2312、微软雅黑。海淀转换器在运行前会校验字体是否可用。
- **Git：** 在本地提交。除非明确要求，否则不要推送到 `zksk` 远程仓库。
- **gitignore：** `render_*/` 目录、`~$*`（Office 临时文件）、`*.tmp`、`Thumbs.db`、`.DS_Store`。
- **启动器：** 在 Windows 上优先使用 `.cmd` 而非 `.ps1`（PowerShell 执行策略可能阻止 `.ps1`）。
- **中文标点：** 所有中文文本必须使用全角（全角）标点符号，尤其是引号用 `""` 而非 `""`。

## 目录结构

- **根目录：** 通用报告（统战、台湾舆情、社媒观点）及通用 `md_to_word_report` 转换器。
- **`北京AI产业/`：** 北京 AI 产业发展报告 —— Markdown 草稿 + 最终 DOCX。
- **`海淀周报/`：** 每周海淀意识形态报告（按日期编号 `YYYYMMDD.md`），及专用 `md转Word工具包/` 转换器。
- **`摘编/`：** 境外敏感信息专报 —— 入册写作和摘编压缩，含专用转换工具、写作 SOP 和模板。
- **`公众号/`：** 口碑周报及舆情热点文章，含周报素材和配图。
- **`日菲/`：** 日菲 EEZ 划界涉台舆情专报及相关素材。
- **`统战6月热点/`：** 统战领域 6 月热点事件舆情报告。
- **`统战歪曲/`：** 赖清德当局污名化统战相关舆情专报。
- **`台湾联系窗口/`：** 台当局涉大陆情报收集舆情及社媒观点。
- **`example/`：** 参考范文，供写作时借鉴格式和文风。
- **`render_*/`：** 临时渲染/输出目录（gitignored）。
- **`PROJECT_MEMORY.md`：** 持久化项目笔记（编码、字体规则、Git 策略）。
