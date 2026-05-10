"""
Semantic Scholar search helper — queries the S2 API and returns structured results.
Usage: python semantic_scholar_search.py "keyword1 keyword2" [--max 15] [--year 2023-] [--api-key KEY]
       python semantic_scholar_search.py "main query" --max 10 --multi "alt query 1" "alt query 2"

Supports S2_API_KEY env var. With key: 10 req/s; without key: 1 req/s with longer backoff.
API keys are free: https://www.semanticscholar.org/product/api#api-key
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"

MAX_RETRIES_WITH_KEY = 3
MAX_RETRIES_NO_KEY = 5
BASE_DELAY = 2
INTER_QUERY_DELAY_NO_KEY = 3  # seconds between queries without key
INTER_QUERY_DELAY_WITH_KEY = 1  # seconds between queries with key


def _ssl_ctx():
    """Create a default SSL context. No probe — SSL errors are handled at urlopen level."""
    return ssl.create_default_context()


def _ssl_fallback_ctx():
    """Create a relaxed SSL context that skips certificate verification."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _get_retries(api_key: str | None) -> int:
    return MAX_RETRIES_WITH_KEY if api_key else MAX_RETRIES_NO_KEY


def search(query: str, max_results: int = 15, year: str = None, api_key: str | None = None) -> list[dict]:
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,authors,year,venue,citationCount,url,externalIds,abstract",
    }
    if year:
        params["year"] = year

    url = f"{S2_API}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": "literature-scout/1.0"}
    if api_key:
        headers["x-api-key"] = api_key

    req = urllib.request.Request(url, headers=headers)
    max_retries = _get_retries(api_key)
    data = None
    ssl_fallback = False

    for attempt in range(max_retries):
        try:
            ctx = _ssl_fallback_ctx() if ssl_fallback else _ssl_ctx()
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except ssl.SSLCertVerificationError:
            if not ssl_fallback:
                print("Info: SSL cert verification failed, retrying with relaxed SSL", file=sys.stderr)
                ssl_fallback = True
                continue
            raise
        except urllib.error.HTTPError as e:
            if e.code == 429:
                delay = BASE_DELAY * (2 ** attempt)
                print(f"Warning: S2 API 429, retrying in {delay}s (attempt {attempt+1}/{max_retries})", file=sys.stderr)
                time.sleep(delay)
            else:
                raise
        except urllib.error.URLError as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e.reason) and not ssl_fallback:
                print("Info: SSL cert verification failed, retrying with relaxed SSL", file=sys.stderr)
                ssl_fallback = True
                continue
            delay = BASE_DELAY * (2 ** attempt)
            print(f"Warning: S2 network error ({e.reason}), retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
    else:
        print(f"Error: S2 API failed after {max_retries} retries", file=sys.stderr)
        return []

    if data is None:
        return []

    results = []
    for paper in data.get("data", []):
        if not paper:
            continue

        authors = [a.get("name", "") for a in (paper.get("authors") or [])[:5]]

        ext_ids = paper.get("externalIds") or {}
        arxiv_id = ext_ids.get("ArXiv", "")
        doi = ext_ids.get("DOI", "")

        link = paper.get("url", "")
        if arxiv_id:
            link = f"https://arxiv.org/abs/{arxiv_id}"
        elif doi:
            link = f"https://doi.org/{doi}"

        abstract = (paper.get("abstract") or "")[:300]

        results.append({
            "title": paper.get("title", ""),
            "authors": authors,
            "year": paper.get("year"),
            "venue": paper.get("venue", ""),
            "citations": paper.get("citationCount", 0),
            "arxiv_id": arxiv_id,
            "doi": doi,
            "abstract": abstract,
            "link": link,
        })

    return results


def multi_search(queries: list[str], max_results: int = 15, year: str = None, api_key: str | None = None) -> list[dict]:
    """Run multiple queries with dedup by arXiv ID or DOI."""
    seen = set()
    all_results = []
    delay = INTER_QUERY_DELAY_WITH_KEY if api_key else INTER_QUERY_DELAY_NO_KEY

    for i, q in enumerate(queries):
        if i > 0:
            time.sleep(delay)
        try:
            results = search(q, max_results, year, api_key)
        except Exception as e:
            print(f"Warning: query '{q}' failed: {e}", file=sys.stderr)
            continue

        for r in results:
            key = r.get("arxiv_id") or r.get("doi") or r["title"].lower()
            if key not in seen:
                seen.add(key)
                all_results.append(r)

    return all_results


def main():
    parser = argparse.ArgumentParser(description="Search Semantic Scholar")
    parser.add_argument("query", help="Search keywords")
    parser.add_argument("--max", type=int, default=15, help="Max results per query")
    parser.add_argument("--year", default=None, help="Year filter (e.g. '2023-' or '2023-2025')")
    parser.add_argument("--api-key", default=None, help="S2 API key (or set S2_API_KEY env var)")
    parser.add_argument("--multi", nargs="*", help="Additional queries to merge (dedup by ID)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("S2_API_KEY", "") or None

    sys.stdout.reconfigure(encoding="utf-8")

    if args.multi:
        queries = [args.query] + args.multi
        results = multi_search(queries, args.max, args.year, api_key)
    else:
        results = search(args.query, args.max, args.year, api_key)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
