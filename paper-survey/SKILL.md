---
name: paper-survey
license: MIT
version: "1.0.0"
description: Paper management and literature survey workflow. Organize PDF papers into a categorized repository (papers/) and conduct topic-based literature surveys (literature-survey/) with structured reading notes. Use this skill when: adding new papers that need classification and renaming, starting a literature survey on a topic, searching or listing existing papers, or writing paper summaries. Trigger on explicit action words: "归档", "整理论文", "rename paper", "organize paper", "archive paper", "调研", "文献调研", "survey papers on", "list papers", "search papers", "写解读", "paper summary", "论文分类", or when the user provides a PDF path and asks to classify/archive it. Do NOT trigger for casual mentions of "paper" or "论文" in general conversation (e.g., "I read a paper about X", "这篇 paper 的方法有问题").
---

# Paper-Survey: Paper Organization & Literature Survey

This skill manages two cooperating workspaces:
- **papers/** — Single-source PDF repository (organized by research direction)
- **literature-survey/** — Survey pipeline (topic-based reading notes and syntheses)

Core principle: **Single-source storage + multi-dimensional indexing**. PDFs live in `papers/` only; survey notes link to originals via relative paths, never copy PDFs.

## Workflow 1: Archive a New Paper

When the user provides a new PDF (path or file):

### Step 1: Extract metadata

Use pypdf to extract metadata. **Important**: PDF `metadata.title/author` fields are frequently empty (especially arXiv papers). Always extract from page text as the primary source.

```python
from pypdf import PdfReader
import sys, re
sys.stdout.reconfigure(encoding='utf-8')

r = PdfReader("<path>")
meta_title = (r.metadata.title or "").strip()
meta_author = (r.metadata.author or "").strip()
first_page = r.pages[0].extract_text() or ""

# Use metadata if populated, otherwise parse from page text
if meta_title and len(meta_title) > 5:
    print("Title:", meta_title)
else:
    # Fallback: first non-empty line of reasonable length is usually the title
    for line in first_page.split("\n"):
        line = line.strip()
        if line and len(line) > 10 and len(line) < 200:
            print("Title (from page):", line)
            break

if meta_author and meta_author not in ("CNKI",):
    print("Authors:", meta_author)

print("Pages:", len(r.pages))
print("---Abstract---")
print(first_page[:800])
```

**常见问题处理**：
- PDF metadata 为空 → 从正文第一页提取（arXiv 论文几乎都是这种情况）
- CNKI 论文 metadata.author 返回 "CNKI" → 忽略，从正文解析作者
- pypdf 报 `Multiple definitions in dictionary` 警告 → 正常，不影响提取
- 中文论文编码 → `sys.stdout.reconfigure(encoding='utf-8')` 确保不乱码

### Step 2: Determine category

Read the `papers/CLAUDE.md` file in the user's project — it defines the category numbering system. If no CLAUDE.md exists, suggest creating one based on the user's research directions.

General classification principles:
- **Application-first**: If a methods paper is designed for a specific domain, file it under that domain, not under general methods
- **Core contribution rule**: When the boundary is fuzzy, ask: is the core contribution the method or the application? Method → general methods category; Application → domain category
- **Non-papers go to reference**: Slides, reading lists, course materials → a reference/misc category
- **New category if needed**: If no existing category fits, create a new numbered directory and update the CLAUDE.md

### Step 3: Rename

Format: `[Year]-[FirstAuthor]-[ShortName].pdf`

- **Year**: Publication year (conference/journal); for preprints only, use the arXiv submission year
- **Author**: English papers use last name (Ho, Song, Price); CJK papers use full name (熊喆, 李宇翔)
- **ShortName**: Use the paper's own coined term if available (DDPM, ResNet, BERT, LaDCast); otherwise method+task (MultiModalGNN-OffGrid); for surveys append "Review"

Examples:
- `2020-Ho-DDPM.pdf`
- `2016-He-ResNet.pdf`
- `2024-Price-GenCast.pdf`
- `2025-Zhuang-LaDCast.pdf`
- `2023-Zheng-TreeCrown-Review.pdf`
- `2021-熊喆-对流解析青藏高原降水.pdf`

### Step 4: Move

Move to `papers/<category-dir>/`. **Before moving, check for duplicates**:

```bash
# Check by filename pattern (author + short name)
ls papers/*/*<Author>*<ShortName>* 2>/dev/null

# Check by exact filename
ls papers/<category>/<Year>-<Author>-<ShortName>.pdf 2>/dev/null
```

If duplicate found → report to user, skip moving. Never overwrite existing files.

**Cross-platform path note**: Use `cp` instead of `mv` to copy files, which avoids cross-filesystem move issues (e.g. Windows temp dir on a different drive from the target).

### Step 5: Report

Tell the user: original filename → new path. If duplicate found, report: "⚠️ 已存在，跳过: <existing-path>"

## Workflow 2: Topic Survey

When the user wants to start a literature survey on a topic:

### Step 1: Create topic directory

Under `literature-survey/topics/`, create a new directory with kebab-case naming:
```
literature-survey/topics/<topic-name>/
├── notes.md       # Survey synthesis
└── summaries/     # Individual paper summaries
```

### Step 2: Identify relevant papers

Scan `papers/` for papers related to the topic. Search methods (按优先级):
1. **By directory name**: category names often indicate topic relevance
2. **By filename**: use Glob `**/*<keyword>*` to match author names and short names
3. **By user specification**: if user names specific papers, locate them directly

Note: Grep cannot search inside PDF content. For content-based search, use pypdf to extract text first, or rely on filename-based matching.

### Step 3: Read and summarize

For each paper, create a summary file in `summaries/` with naming: `<author>-<year>-<short>.md`

Use this template:

```markdown
# <Paper Title>

## Basic Info
- **Title**:
- **Authors**:
- **Venue**:
- **Year**:
- **PDF**: [<ShortName>](<relative-path-to-papers/>)

## Core Problem
<!-- What problem does this paper solve? -->

## Key Method
<!-- What is the core method? How does it work? -->

## Main Results
<!-- Key experimental results. How well does it perform? -->

## Limitations & Insights
<!-- Limitations, takeaways, future directions -->
```

PDF linking rules:
- From `summaries/`: `[ShortName](../../../papers/<category>/<file>.pdf)`
- Summary filenames should correspond to the PDF naming in papers/ (same author, year, short name)

### Step 4: Write synthesis

In `notes.md`, write the survey synthesis with this structure:
1. **Topic overview**: scope and core questions
2. **Core papers**: each with links to summary and PDF
3. **Key findings**: synthesized insights
4. **Future directions**: as a checkbox list

### Cross-topic references

The same paper may appear in multiple topics:
- Different perspectives → write separate summaries in each topic's `summaries/`
- Same perspective → write once, link from other topic's `notes.md`

## Workflow 3: Reading Status

Track reading progress for papers in the repository.

### Status file

`papers/_reading_status.json` — single source of truth for reading status.

Format:
```json
{
  "01_扩散模型理论/2020-Ho-DDPM.pdf": "done",
  "02_扩散模型x气象/2024-Price-GenCast.pdf": "reading",
  "03_气象大模型/2025-Zhuang-LaDCast.pdf": "todo"
}
```

Status values:
- `todo` — archived but not yet read
- `reading` — currently reading / in progress
- `done` — finished reading (may or may not have a summary)

### Mark status

When user says "标记这篇论文为已读", "mark as reading", "这篇在读", etc.:

```bash
# Read current status
cat papers/_reading_status.json

# Update: use Python one-liner to modify JSON safely
python -c "
import json, sys
status_file = 'papers/_reading_status.json'
with open(status_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
data['<category>/<filename>.pdf'] = '<new-status>'
with open(status_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print('Updated: <filename> -> <new-status>')
"
```

### Auto-set on archive

When Workflow 1 archives a new paper, automatically set its status to `todo` in `_reading_status.json`.

### Auto-set on survey

When Workflow 2 creates a paper summary, automatically set that paper's status to `done` in `_reading_status.json`.

### View status

When user says "阅读进度", "reading progress", "哪些论文没读", etc.:

1. Read `_reading_status.json`
2. Scan `papers/` for all PDFs
3. **Auto-calibrate** before display:
   - PDFs not in status file → add as `todo`
   - Status entries whose PDF no longer exists → remove
4. Write calibrated result back to `_reading_status.json`
5. Display grouped by category:

```
01_扩散模型理论/
  [todo]  2020-Ho-DDPM.pdf
  [done]  2021-Song-DDIM.pdf
02_扩散模型x气象/
  [reading] 2024-Price-GenCast.pdf
  [todo]   2024-Another-Paper.pdf

Progress: 12 done / 3 reading / 38 todo (53 total)
```

### Initialize status file

If `_reading_status.json` does not exist, create it by scanning all PDFs in `papers/` and setting them to `todo`. Also check `literature-survey/topics/*/summaries/` — any paper that has a corresponding summary file gets set to `done` instead.

## Workflow 4: Search & List

### List all papers

Scan `papers/` for all PDFs, then auto-calibrate `_reading_status.json` (add missing, remove deleted), display grouped by directory:
```
01_<category>/
  2020-Ho-DDPM.pdf
  2021-Song-DDIM.pdf
02_<category>/
  ...
```

### Search by criteria

Support searching by:
- **Author**: the author field in filenames → `Glob: **/*<Author>*`
- **Year**: the year field in filenames → `Glob: **/*<Year>*`
- **Keyword**: the short name portion of filenames → `Glob: **/*<Keyword>*`
- **Category**: specific directory number or name → `Glob: papers/<category>/*`

**重要**：Grep 无法搜索 PDF 二进制内容。搜索论文内容需先 pypdf 提取文本，或依赖文件名匹配。

### Find survey notes

Scan `literature-survey/topics/` for all `notes.md` and `summaries/` files, list existing survey topics and summaries.

## Prohibitions

- Never store PDF copies outside of papers/
- Never use spaces, exclamation marks, or parentheses in filenames
- Never keep duplicate copies of the same paper
- Never leave unclassified papers in the papers/ root directory
- Never rename without first extracting metadata via pypdf
- Never overwrite an existing PDF — always check for duplicates first
