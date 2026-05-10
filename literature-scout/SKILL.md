---
name: literature-scout
license: MIT
version: "1.0.0"
description:
  Automated literature collection from the web. Searches academic papers (arXiv, Semantic Scholar, DBLP)
  and related open-source projects (GitHub) for given research keywords.
  Use this skill when: the user wants to FIND or DISCOVER papers/repos on a topic from the web,
  or mentions "搜文献", "找论文", "literature search", "paper search", "scout", "文献搜集",
  "论文搜索", "find papers on", "search papers", "collect literature", or asks to discover
  what's new in a research area. Trigger even for casual mentions like "帮我找一下 LLM serving 的论文"
  or "最近有什么新论文".
  Do NOT trigger for: organizing/archiving existing PDFs, writing survey notes, or renaming/moving
  papers already on disk — those belong to the paper-survey skill.
---

# Literature Scout: Automated Web Literature Collection

Given research keywords, systematically search the web for academic papers and open-source projects, produce a structured report, and optionally archive to papers/.

**与 paper-survey 的边界**：literature-scout = 从网上发现；paper-survey = 本地归档和调研。

## Workflow

### Step 1: Parse the query

Extract:
- **Keywords**: core research terms
- **Scope hints**: conferences, year range, constraints
- Default: quick scan (top 15-20 papers, 8-10 repos)

Ambiguous keywords → ask user before proceeding.

### Step 2: Check cache

```bash
python "${SKILL_DIR}/scripts/merge_results.py" --cache-hit "<keywords> --year <year> --venue <venue>"
```

The cache key is derived from the full query string including parameters, so `"LLM routing --year 2024-"` and `"LLM routing --year 2025-"` produce different cache entries. Pass the same parameter string used in the actual search.

If cache hit → skip API calls, use cached results. If miss → proceed to Step 3.

### Step 3: Search academic papers (main agent, no sub-agents)

Run all three scripts directly in the main agent. These are pure API calls — no web-access needed for script execution.

#### 3a. arXiv (default: relevance sort, field prefixes)

```bash
python "${SKILL_DIR}/scripts/arxiv_search.py" "ti:<keyword1> AND ti:<keyword2>" --max 12 --sort-by relevance --multi "abs:<k1> AND abs:<k2> AND abs:<k3>"
```

Field prefixes: `ti:` (title), `abs:` (abstract), `au:` (author), `cat:` (category)

#### 3b. Semantic Scholar (with optional API key)

```bash
# Without key (1 req/s, longer backoff):
python "${SKILL_DIR}/scripts/semantic_scholar_search.py" "<keywords>" --max 12 --year 2023-

# With key (10 req/s, faster):
python "${SKILL_DIR}/scripts/semantic_scholar_search.py" "<keywords>" --max 12 --year 2023- --api-key $S2_API_KEY
```

Free API key: https://www.semanticscholar.org/product/api#api-key
Set env var: `S2_API_KEY=<your-key>` for automatic use.

#### 3c. DBLP (no auth, no rate limit, good for conference papers)

```bash
python "${SKILL_DIR}/scripts/dblp_search.py" "<keywords>" --max 15
# Venue filter:
python "${SKILL_DIR}/scripts/dblp_search.py" "<keywords>" --max 10 --venue NeurIPS
```

### Step 4: Search open-source projects (GitHub MCP)

Use GitHub MCP search_repositories directly:

```
mcp__plugin_github_github__search_repositories:
  query: "<keywords>"
  sort: stars
  order: desc
  perPage: 10
```

Run 2-3 queries with different keyword combinations for coverage.

### Step 5: Merge and deduplicate

Save each source's output to temp files, then merge:

```bash
python "${SKILL_DIR}/scripts/arxiv_search.py" "..." > /tmp/arxiv.json
python "${SKILL_DIR}/scripts/semantic_scholar_search.py" "..." > /tmp/s2.json
python "${SKILL_DIR}/scripts/dblp_search.py" "..." > /tmp/dblp.json
python "${SKILL_DIR}/scripts/merge_results.py" /tmp/arxiv.json /tmp/s2.json /tmp/dblp.json -o /tmp/merged.json
```

Then cache the result:

```bash
python "${SKILL_DIR}/scripts/merge_results.py" --cache-store "<keywords>" < /tmp/merged.json
```

Merge script dedup logic (priority order):
1. **DOI match** (most reliable cross-source key): same normalized DOI = same paper
2. **arXiv ID match**: same arXiv ID = same paper
3. **Title similarity**: word-overlap >= 70% → merge, keeping more complete fields (citations, venue, DOI)
- Sort: venue prestige, then citations desc, then recency

### Step 6: Check local papers/ for already-archived papers

Before generating the report, scan the project's `papers/` directory to mark papers that are already archived:

```bash
# List all existing PDFs in papers/
find papers/ -name "*.pdf" -type f 2>/dev/null
```

Match logic (best-effort, no false positives):
1. **arXiv ID match**: If a search result has an arXiv ID, check if any filename in papers/ contains that ID pattern (e.g., `2401.12345`)
2. **Author+ShortName match**: Parse existing filenames `[Year]-[Author]-[ShortName].pdf`, check if the search result's first author + title short name matches

For each matched paper, add `"archived": true` and `"archived_path": "<relative-path>"` to the merged result. The report will show an "Archived" badge for these papers, so users know they don't need to download again.

### Step 7: Generate report

**Note**: The cache key includes the full query string (keywords + all parameters like --year, --venue, --max), so changing parameters produces a fresh cache entry.

```bash
mkdir -p literature-scout/reports
```

Write to `literature-scout/reports/<YYYY-MM-DD>-<keywords-slug>.md`:

```markdown
# Literature Scout Report: <Keywords>

**Generated**: <YYYY-MM-DD>
**Keywords**: <keywords>

## Search Strategy

| Source | Query | Parameters | Status |
|--------|-------|------------|--------|
| arXiv | `ti:<k1> AND ti:<k2>` | --max 12 --sort-by relevance --multi `abs:<k1> AND abs:<k2> AND abs:<k3>` | ✓ / ✗ |
| Semantic Scholar | `<keywords>` | --max 12 --year 2023- | ✓ / ✗ (429) |
| DBLP | `<keywords>` | --max 15 | ✓ / ✗ |
| GitHub | `<keywords>` | sort:stars, perPage:10 | ✓ / ✗ |

---

## Academic Papers

| # | Title | Authors | Venue/Year | Citations | Archived | Link |
|---|-------|---------|------------|-----------|----------|------|

<!-- Archived = "✓ <path>" if paper exists in papers/, otherwise blank -->

### Notable Papers
<!-- Top 5: 2-3 sentence abstract each; mark [已归档] if archived -->

---

## Open-Source Projects

| # | Repository | Stars | Description | Link |
|---|-----------|-------|-------------|------|

---

## Summary
- **Total papers**: N (already archived: M) | **Total repos**: K
- **Top venues**: ...
- **Key trends**: ...
```

The **Search Strategy** table records every query actually sent, so the search can be reproduced or adjusted later.

### Step 8: Archive to papers/ (联动 paper-survey)

After the report is generated, present the archive options to the user.

#### Present archive candidates

From the report's paper list, filter out papers already marked as "Archived". Present the remaining as numbered candidates:

```
Archive candidates (not yet in papers/):
  [1] DiffDA: a Diffusion Model for Weather-scale Data Assimilation (arXiv 2024)
  [2] OmniCast: A Masked Latent Diffusion Model for Weather Forecasting (arXiv 2025)
  [3] ...
```

#### User selects papers to archive

Accept these formats:
- **Individual**: "归档 1 3 5" or "archive 1,3,5"
- **Range**: "归档 1-5" or "archive all"
- **All unarchived**: "全部归档" or "archive all"

#### Archive each selected paper

For each paper, follow paper-survey Workflow 1:
1. Read `papers/CLAUDE.md` → determine target directory
2. Scan target dir → skip if already exists
3. Download: `curl -L -o "<dir>/<Year>-<Author>-<ShortName>.pdf" "https://arxiv.org/pdf/<id>"`
   - For non-arXiv papers, use DOI link or provide the URL for the user to download manually
4. Naming: `[Year]-[FirstAuthor]-[ShortName].pdf` (自造词优先 → 方法+任务)
5. Update `_reading_status.json` → set to `todo`
6. Update report → mark paper as "Archived" in the table

#### Report results

```
Archive results:
  ✓ 2024-Huang-DiffDA.pdf → 02_扩散模型x气象/
  ✓ 2025-Nguyen-OmniCast.pdf → 03_气象大模型/
  ✗ Paper 3: no arXiv ID or direct PDF link, manual download needed
    → Link: https://doi.org/10.1234/...
```

## Config

| Variable | Purpose | Default |
|----------|---------|--------|
| `S2_API_KEY` | Semantic Scholar API key (free, 10 req/s) | none (1 req/s) |
| `LITSCOUT_CACHE_TTL` | Cache TTL in seconds | 604800 (7 days) |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| arXiv returns irrelevant papers | Use `ti:` field prefix + `--sort-by relevance` |
| S2 429 rate limit | Set `S2_API_KEY` env var; or rely on arXiv + DBLP fallback |
| DBLP returns too broad results | Use `--venue` filter for specific conferences |
| Cache stale | Delete `literature-scout/cache/*.json` or wait for TTL |
| PDF download 404 | Skip paper, mark "下载失败" in report, provide link |
