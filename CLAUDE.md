# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This is a Chinese public-opinion report (舆情报告) workspace. The core workflow is: write reports in Markdown → convert to formatted `.docx` for submission.

## Key conversion tools

Two separate Markdown-to-DOCX pipelines serve different report types:

### 1. Root-level general converter (`md_to_word_report.py`)

For "简报" (brief) style reports. Supports two body-size presets:
- `small2` (小二/18pt) — title 二号, H1 小二, body 小二
- `3` (三号/16pt) — title 小二, H1 小二, body 三号

L2+ headings use the body size and are bold. Usage:

```bash
# Via the launcher (preferred on Windows):
md_to_word_report.cmd input.md [-o output.docx] [--body-size small2|3] [--filename-title]

# Direct:
python md_to_word_report.py input.md [-o output.docx] [--body-size small2|3]
```

### 2. 海淀周报 converter (`海淀周报/md转Word工具包/convert.py`)

A stricter converter for the Haidian weekly ideological report (意识形态周报). Enforces precise formatting:
- A4 page, margins: top/bottom 2.54 cm, left/right 3.18 cm
- Title: 方正大标宋简体 二号, centered, followed by one blank line
- H1 headings: 黑体 三号, 2-char indent
- Body: 仿宋_GB2312 三号, justified, 2-char first-line indent, 28pt exact line spacing
- Tables: 微软雅黑 10pt body / 11pt bold header, fixed column widths
- Auto page numbers in footer

**Strict parsing rules:** Only `#` (H1) is supported. Text that looks like a section heading ("一、...") without `#` causes an error. Images must be on their own line. Network images are rejected.

```bash
# GUI file-picker (double-click the .cmd):
一键转Word.cmd

# CLI:
python convert.py INPUT.md [-o OUTPUT.docx] [--force] [--no-open]

# Dependencies (auto-installed by .cmd on first run):
pip install python-docx Pillow
```

## Project conventions

- **Encoding:** All Markdown files are UTF-8 with BOM (`utf-8-sig`). The converters read and write UTF-8.
- **Fonts:** Required Windows fonts — 方正小标宋简体/方正大标宋简体, 黑体, 仿宋_GB2312, 微软雅黑. The 海淀 converter validates font availability before running.
- **Git:** Commit locally. Do not push to the `zksk` remote unless explicitly asked.
- **gitignore:** `render_*/` directories, `~$*` (Office temp files), `*.tmp`, `Thumbs.db`, `.DS_Store`.
- **Launchers:** Prefer `.cmd` over `.ps1` on Windows (PowerShell execution policy may block `.ps1`).

## Directory structure

- **Root:** General reports (统战, 台湾舆情, 社媒观点) and the general `md_to_word_report` converter.
- **`北京AI产业/`:** Reports on Beijing AI industry development — Markdown drafts + final DOCX.
- **`海淀周报/`:** Weekly Haidian ideological reports (numbered by date `YYYYMMDD.md`), plus the dedicated `md转Word工具包/` converter.
- **`render_*/`:** Temporary rendering/output directories (gitignored).
- **`PROJECT_MEMORY.md`:** Persistent project notes (encoding, font rules, Git policy).
