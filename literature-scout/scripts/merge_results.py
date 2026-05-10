"""
Merge multi-source search results with deduplication.
Usage: python merge_results.py arxiv.json s2.json dblp.json [--output merged.json]

Also provides a cache layer:
  python merge_results.py --cache-hit "LLM routing" [--ttl 604800]
  python merge_results.py --cache-store "LLM routing" merged.json

Cache files stored in literature-scout/cache/ with TTL (default 7 days).
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
DEFAULT_TTL = 7 * 24 * 3600  # 7 days


def _normalize_title(title: str) -> str:
    """Lowercase, remove punctuation and extra spaces for fuzzy matching."""
    t = title.lower().strip()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t


def _title_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity (0-1)."""
    wa = set(_normalize_title(a).split())
    wb = set(_normalize_title(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa | wb), 1)


def _cache_key(query: str) -> str:
    return hashlib.md5(query.lower().strip().encode()).hexdigest()


def cache_hit(query: str, ttl: int = DEFAULT_TTL) -> list[dict] | None:
    """Check if cached results exist and are fresh. Returns results or None.

    The cache key includes the full query string (keywords + parameters),
    so different --year or --venue values produce different cache entries.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{_cache_key(query)}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if time.time() - cached.get("timestamp", 0) > ttl:
            return None
        return cached.get("results", [])
    except (json.JSONDecodeError, OSError):
        return None


def cache_store(query: str, results: list[dict]) -> None:
    """Store results in cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{_cache_key(query)}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"query": query, "timestamp": time.time(), "results": results}, f, ensure_ascii=False, indent=2)


def _normalize_doi(doi: str) -> str:
    """Normalize DOI to lowercase, strip leading 'https://doi.org/' and trailing version."""
    d = doi.lower().strip()
    d = re.sub(r'^https?://doi\.org/', '', d)
    # Remove version suffix like .v1, .v2 (some sources append these)
    d = re.sub(r'\.v\d+$', '', d)
    return d


def _find_index_by_arxiv(deduped: list[dict], arxiv_id: str) -> int:
    """Find the index of a paper in deduped list by its arXiv ID."""
    for i, p in enumerate(deduped):
        if p.get("arxiv_id") == arxiv_id:
            return i
    return -1


def merge(file_paths: list[str], title_threshold: float = 0.7) -> list[dict]:
    """Merge multiple JSON result files, deduplicate, sort."""
    all_papers = []
    for fp in file_paths:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                all_papers.extend(data)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: failed to read {fp}: {e}", file=sys.stderr)

    # Dedup priority: DOI > arXiv ID > title similarity
    seen_doi = {}
    seen_arxiv = set()
    seen_titles = []
    deduped = []

    for paper in all_papers:
        doi = _normalize_doi(paper.get("doi", ""))
        arxiv_id = paper.get("arxiv_id", "")
        title = paper.get("title", "")

        # 1. DOI match (most reliable cross-source key)
        if doi and doi in seen_doi:
            target = deduped[seen_doi[doi]] if seen_doi[doi] < len(deduped) else None
            if target:
                _merge_fields(deduped, paper, seen_doi[doi], "doi", target_paper=target)
                # Register any new arXiv ID from this paper into the index
                if arxiv_id and arxiv_id not in seen_arxiv:
                    seen_arxiv.add(arxiv_id)
            continue

        # 2. arXiv ID match
        if arxiv_id and arxiv_id in seen_arxiv:
            _merge_fields(deduped, paper, arxiv_id, "arxiv_id")
            # Register any new DOI from this paper into the index
            if doi and doi not in seen_doi:
                seen_doi[doi] = _find_index_by_arxiv(deduped, arxiv_id)
            continue

        # 3. Title similarity match
        norm_title = _normalize_title(title)
        is_dup = False
        for existing_norm, existing_paper in seen_titles:
            if _title_similarity(title, existing_norm) >= title_threshold:
                _merge_fields(deduped, paper, None, None, existing_paper)
                # Register new identifiers from this paper
                if doi and doi not in seen_doi:
                    idx = deduped.index(existing_paper) if existing_paper in deduped else -1
                    if idx >= 0:
                        seen_doi[doi] = idx
                if arxiv_id and arxiv_id not in seen_arxiv:
                    seen_arxiv.add(arxiv_id)
                is_dup = True
                break

        if is_dup:
            continue

        # New paper
        if doi:
            seen_doi[doi] = len(deduped)
        if arxiv_id:
            seen_arxiv.add(arxiv_id)
        seen_titles.append((norm_title, paper))
        deduped.append(paper)

    # Sort: venue prestige, then citations, then recency
    # Keep in sync with references/top-venues.md
    venue_rank = {
        # Tier 0: Flagship journals
        "nature": 0, "science": 0,
        # Tier 1: Top ML/AI conferences + Top systems
        "icml": 1, "neurips": 1, "iclr": 1,
        "osdi": 1, "sosp": 1,
        # Tier 2: Top domain conferences + Top journals + HPC
        "cvpr": 2, "iccv": 2, "eccv": 2,
        "acl": 2, "emnlp": 2,
        "mlsys": 2, "nsdi": 2, "atc": 2, "eurosys": 2,
        "sc": 2, "isc": 2,
        "jmlr": 2, "tpami": 2, "nature machine intelligence": 2, "pnas": 2,
        # Tier 3: Strong but broader venues
        "aaai": 3, "ijcai": 3,
        "aistats": 3, "uai": 3,
        "kdd": 3, "www": 3,
        "ipdps": 3, "naacl": 3, "tip": 3,
    }

    def _sort_key(p):
        v = (p.get("venue") or "").lower()
        rank = min(venue_rank.get(k, 99) for k in venue_rank if k in v) if any(k in v for k in venue_rank) else 99
        citations = p.get("citations", 0) or 0
        year = p.get("year") or p.get("published", "")[:4] or "0"
        try:
            year = int(str(year)[:4])
        except ValueError:
            year = 0
        return (rank, -citations, -year)

    deduped.sort(key=_sort_key)
    return deduped


def _merge_fields(deduped_list, new_paper, match_id, match_field, target_paper=None):
    """Merge fields from new_paper into existing entry. Fill in missing fields."""
    if target_paper:
        existing = target_paper
    else:
        for p in deduped_list:
            if match_field and p.get(match_field) == match_id:
                existing = p
                break
        else:
            return

    # Fill missing fields from new paper
    for key in ("citations", "venue", "doi", "arxiv_id", "abstract", "link"):
        if not existing.get(key) and new_paper.get(key):
            existing[key] = new_paper[key]
    # Keep longer authors list
    if len(new_paper.get("authors", [])) > len(existing.get("authors", [])):
        existing["authors"] = new_paper["authors"]
    # Keep higher citation count
    if new_paper.get("citations", 0) > (existing.get("citations", 0) or 0):
        existing["citations"] = new_paper["citations"]


def main():
    parser = argparse.ArgumentParser(description="Merge and cache search results")
    parser.add_argument("files", nargs="*", help="JSON result files to merge")
    parser.add_argument("--output", "-o", default=None, help="Output file (default: stdout)")
    parser.add_argument("--cache-hit", metavar="QUERY", default=None, help="Check cache for query")
    parser.add_argument("--cache-store", metavar="QUERY", default=None, help="Store results in cache")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL, help="Cache TTL in seconds")
    parser.add_argument("--threshold", type=float, default=0.7, help="Title similarity threshold for dedup")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")

    # Cache hit mode
    if args.cache_hit:
        results = cache_hit(args.cache_hit, args.ttl)
        if results is not None:
            print(json.dumps({"cache": "hit", "results": results}, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"cache": "miss"}, ensure_ascii=False, indent=2))
        return

    # Cache store mode
    if args.cache_store:
        data = json.load(sys.stdin) if not sys.stdin.isatty() else []
        if isinstance(data, list):
            cache_store(args.cache_store, data)
        elif isinstance(data, dict) and "results" in data:
            cache_store(args.cache_store, data["results"])
        print(f"Cached {len(data) if isinstance(data, list) else len(data.get('results', []))} results", file=sys.stderr)
        return

    # Merge mode
    if not args.files:
        print("Error: provide JSON files to merge, or use --cache-hit/--cache-store", file=sys.stderr)
        sys.exit(1)

    results = merge(args.files, args.threshold)
    output = json.dumps(results, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Merged {len(results)} papers -> {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
