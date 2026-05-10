# Paper Survey

Paper management and literature survey workflow for Claude Code. Organize PDFs into a categorized repository, track reading progress, write structured reading notes, and synthesize topic surveys.

## Installation

1. Copy this directory to your Claude Code skills folder:
   ```bash
   cp -r paper-survey ~/.claude/skills/
   ```

2. Install pypdf (required for PDF metadata extraction):
   ```bash
   pip install pypdf
   ```

## Usage

```
/paper-survey 归档这篇论文 /path/to/paper.pdf
/paper-survey 帮我调研 LLM 路由方向的论文
/paper-survey 列出所有论文
/paper-survey 搜索 2024 年的论文
/paper-survey 阅读进度
/paper-survey 标记 GenCast 为已读
```

## Workflows

### 1. Archive a New Paper

Provides a PDF path → the skill extracts metadata (title, authors, abstract), determines category, renames following `[Year]-[Author]-[ShortName].pdf` convention, moves to `papers/<category>/`, and sets reading status to `todo`.

### 2. Topic Survey

Start a survey on a topic → creates topic directory, identifies relevant papers from `papers/`, reads and summarizes each paper, writes synthesis in `notes.md`. Papers with summaries are automatically marked as `done` in reading status.

### 3. Reading Status

Track reading progress via `papers/_reading_status.json`:
- `todo` — archived but not yet read
- `reading` — currently reading
- `done` — finished reading (may or may not have a summary)

Auto-calibration: when viewing progress or listing papers, missing PDFs are added as `todo` and entries for deleted PDFs are removed.

### 4. Search & List

- List all papers grouped by category
- Search by author, year, keyword, or category (filename-based)
- Find existing survey notes

## Directory Structure

```
papers/                          # Single-source PDF repository
├── CLAUDE.md                    # Category definitions and naming rules
├── _reading_status.json         # Reading progress tracker
├── 01_category/                 # Papers organized by research direction
└── ...

literature-survey/
├── CLAUDE.md                    # Survey workspace spec
├── templates/
│   └── paper-summary.md         # Paper summary template
└── topics/
    └── <topic-name>/
        ├── notes.md             # Survey synthesis
        └── summaries/          # Individual paper summaries
```

## Integration with literature-scout

Use [literature-scout](../literature-scout/) to discover papers from the web, then use paper-survey to archive and survey them.

```
/literature-scout LLM routing    → discovers papers
  ↓ report shows archive candidates numbered [1] [2] [3]...
  ↓ user says "归档 1 3" or "全部归档"
/paper-survey                      → downloads, renames, classifies, sets status=todo
  ↓ user starts a topic survey
/paper-survey                      → writes reading notes and synthesis, sets status=done
```

## License

MIT
