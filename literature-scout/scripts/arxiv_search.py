"""
arXiv search helper — queries the arXiv API and returns structured results.
Usage: python arxiv_search.py "ti:LLM AND ti:routing" [--max 15] [--sort-by relevance]

Supports arXiv API query fields: ti: (title), abs: (abstract), au: (author), cat: (category).
If no field prefix given, wraps in all: for backward compatibility.
"""

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

ARXIV_API = "https://export.arxiv.org/api/query"

MAX_RETRIES = 5
BASE_DELAY = 3  # seconds, exponential backoff base


def _ssl_ctx():
    return ssl.create_default_context()


def _ssl_fallback_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


def search(query: str, max_results: int = 15, sort_by: str = "relevance") -> list[dict]:
    if not any(query.startswith(p) for p in ("ti:", "abs:", "au:", "cat:", "all:")):
        query = f"all:{query}"

    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance" if sort_by == "relevance" else "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"

    ssl_fallback = False
    data = None

    for attempt in range(MAX_RETRIES):
        try:
            ctx = _ssl_fallback_ctx() if ssl_fallback else _ssl_ctx()
            req = urllib.request.Request(url, headers={"User-Agent": "literature-scout/1.0"})
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                data = resp.read().decode("utf-8")
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
                print(f"Warning: arXiv API 429, retrying in {delay}s (attempt {attempt+1}/{MAX_RETRIES})", file=sys.stderr)
                time.sleep(delay)
            else:
                raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(getattr(e, 'reason', '')) and not ssl_fallback:
                print("Info: SSL cert verification failed, retrying with relaxed SSL", file=sys.stderr)
                ssl_fallback = True
                continue
            delay = BASE_DELAY * (2 ** attempt)
            print(f"Warning: arXiv network error ({e}), retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
    else:
        print(f"Error: arXiv API failed after {MAX_RETRIES} retries", file=sys.stderr)
        return []

    if data is None:
        return []

    root = ET.fromstring(data)
    results = []

    for entry in root.findall("atom:entry", NS):
        title = entry.find("atom:title", NS).text.strip().replace("\n", " ")
        summary = entry.find("atom:summary", NS).text.strip().replace("\n", " ")[:300]
        published = entry.find("atom:published", NS).text[:10]
        arxiv_id = entry.find("atom:id", NS).text.split("/abs/")[-1]

        authors = []
        for author in entry.findall("atom:author", NS):
            name = author.find("atom:name", NS).text.strip()
            authors.append(name)

        categories = []
        for cat in entry.findall("atom:category", NS):
            categories.append(cat.get("term"))

        link = f"https://arxiv.org/abs/{arxiv_id}"

        results.append({
            "title": title,
            "authors": authors[:5],
            "published": published,
            "arxiv_id": arxiv_id,
            "categories": categories,
            "abstract": summary,
            "link": link,
        })

    return results


def multi_search(queries: list[str], max_results: int = 15, sort_by: str = "relevance") -> list[dict]:
    """Run multiple queries, merge and deduplicate by arXiv ID."""
    seen_ids = set()
    all_results = []

    for q in queries:
        try:
            results = search(q, max_results, sort_by)
        except Exception as e:
            print(f"Warning: query '{q}' failed: {e}", file=sys.stderr)
            continue

        for r in results:
            if r["arxiv_id"] not in seen_ids:
                seen_ids.add(r["arxiv_id"])
                all_results.append(r)

        time.sleep(1)  # rate limit between queries

    return all_results


def main():
    parser = argparse.ArgumentParser(description="Search arXiv")
    parser.add_argument("query", help="Search query (supports ti:, abs:, au:, cat: prefixes)")
    parser.add_argument("--max", type=int, default=15, help="Max results per query")
    parser.add_argument("--sort-by", choices=["submitted", "relevance"], default="relevance",
                        help="Sort order (default: relevance)")
    parser.add_argument("--multi", nargs="*", help="Additional queries to merge (dedup by arXiv ID)")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")

    if args.multi:
        queries = [args.query] + args.multi
        results = multi_search(queries, args.max, args.sort_by)
    else:
        results = search(args.query, args.max, args.sort_by)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
