# Literature Scout

Automated literature collection from the web. Searches academic papers (arXiv, Semantic Scholar, DBLP) and open-source projects (GitHub) for given research keywords, produces structured reports with search strategy recording, and integrates with paper-survey for archiving.

## Installation

1. Copy this directory to your Claude Code skills folder:
   ```bash
   cp -r literature-scout ~/.claude/skills/
   ```

2. No additional Python packages required — all scripts use the standard library only.

3. (Optional) Set Semantic Scholar API key for higher rate limits:
   ```bash
   export S2_API_KEY="your-key-here"
   ```
   Free key: https://www.semanticscholar.org/product/api#api-key

## Usage

In Claude Code, invoke the skill with keywords:

```
/literature-scout LLM serving efficiency
/literature-scout 扩散模型气象预报
```

Or use natural language:
- "帮我找一下 LLM serving 的论文"
- "最近有什么新论文 on diffusion model weather forecasting"

## Workflow

1. **Parse query** — extract keywords, scope hints (conferences, year range)
2. **Check cache** — reuse results from previous searches (7-day TTL, keyed by keywords + parameters)
3. **Search papers** — arXiv (relevance sort, retry on 429), Semantic Scholar (with API key), DBLP (no auth)
4. **Search repos** — GitHub API (sorted by stars)
5. **Merge & dedup** — by DOI (priority 1) > arXiv ID > title similarity; sorted by venue prestige
6. **Check local papers/** — mark already-archived papers with "Archived" badge
7. **Generate report** — structured markdown with Search Strategy table, paper list, archive status
8. **Archive** (optional) — batch archive selected papers to papers/, auto-update reading status

## Key Features

- **DOI-first dedup**: cross-source deduplication by DOI, arXiv ID, or title similarity
- **DBLP arXiv ID extraction**: extracts arXiv IDs from both `arxiv.org` URLs and `10.48550/ARXIV.*` DOIs
- **Search Strategy recording**: every query and parameter is logged in the report for reproducibility
- **Local archive check**: papers already in papers/ are marked in the report
- **Batch archive**: archive selected papers by number ("归档 1 3 5"), range ("归档 1-5"), or all
- **429 retry**: all scripts handle rate limits with exponential backoff + SSL fallback
- **Cache**: results cached by full query string (keywords + parameters), 7-day TTL

## Configuration

| Variable | Purpose | Default |
|----------|---------|--------|
| `S2_API_KEY` | Semantic Scholar API key (10 req/s with key vs 1 req/s without) | none |
| `LITSCOUT_CACHE_TTL` | Cache TTL in seconds | 604800 (7 days) |

## Scripts

| Script | Source | Auth | Rate Limit |
|--------|--------|------|------------|
| `arxiv_search.py` | arXiv API | None | ~1 req/s, auto-retry on 429 |
| `semantic_scholar_search.py` | S2 API | Optional API key | 1 req/s (10 req/s with key) |
| `dblp_search.py` | DBLP API | None | None |
| `merge_results.py` | Local merge + cache | N/A | N/A |

### Script Examples

```bash
# arXiv: title search with relevance sort
python scripts/arxiv_search.py "ti:LLM AND ti:routing" --max 15 --sort-by relevance

# arXiv: multi-query with auto dedup
python scripts/arxiv_search.py "ti:GenCast" --multi "ti:DiffCast" "ti:PreDiff" --max 10

# Semantic Scholar: with year filter and API key
python scripts/semantic_scholar_search.py "diffusion weather forecasting" --max 15 --year 2023- --api-key $S2_API_KEY

# DBLP: with venue filter
python scripts/dblp_search.py "model routing LLM" --max 10 --venue NeurIPS

# Merge multiple sources
python scripts/merge_results.py arxiv.json s2.json dblp.json -o merged.json

# Cache operations
python scripts/merge_results.py --cache-hit "LLM routing --year 2024- --venue NeurIPS"
python scripts/merge_results.py --cache-store "LLM routing --year 2024-" < merged.json
```

## Integration with paper-survey

Literature-scout finds papers; paper-survey archives and surveys them.

```
/literature-scout LLM routing    → discovers papers
  ↓ report shows archive candidates numbered [1] [2] [3]...
  ↓ user says "归档 1 3" or "全部归档"
/paper-survey                      → downloads PDFs, renames, classifies
  ↓ user starts a topic survey
/paper-survey                      → writes reading notes and synthesis
```

Reading status (`_reading_status.json`) is automatically updated: new archives set to `todo`, papers with summaries set to `done`.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| SSL certificate errors | Scripts auto-retry with relaxed SSL; no action needed |
| S2 API 429 rate limit | Set `S2_API_KEY` env var; scripts auto-retry with exponential backoff |
| arXiv 429 rate limit | Script auto-retries with exponential backoff (up to 5 attempts) |
| arXiv returns irrelevant papers | Use `ti:` field prefix + `--sort-by relevance` |
| DBLP returns too broad results | Use `--venue` filter for specific conferences |
| Cache stale | Delete `cache/*.json` or wait for TTL expiry |
| Old cache hit with new parameters | Cache key includes full query + parameters; different params = fresh cache |

## License

MIT
