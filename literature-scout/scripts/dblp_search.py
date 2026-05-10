"""
DBLP search helper — queries the DBLP API and returns structured results.
No API key required. No strict rate limit (just be reasonable).
Usage: python dblp_search.py "keyword1 keyword2" [--max 15] [--venue ICML|NeurIPS|...]
"""

import argparse
import json
import re
import ssl
import sys
import urllib.request
import urllib.parse

DBLP_API = "https://dblp.org/search/publ/api"

# Fallback SSL context for environments with cert issues (e.g. corporate proxies)
def _ssl_ctx():
    """Create a default SSL context. No probe — SSL errors are handled at urlopen level."""
    return ssl.create_default_context()


def _ssl_fallback_ctx():
    """Create a relaxed SSL context that skips certificate verification."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def search(query: str, max_results: int = 15, venue: str = None) -> list[dict]:
    params = {
        "q": query,
        "format": "json",
        "h": max_results,
        "f": 0,
    }
    if venue:
        params["q"] = f"{query} venue:{venue}"

    url = f"{DBLP_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "literature-scout/1.0"})

    try:
        ctx = _ssl_ctx()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (ssl.SSLCertVerificationError, urllib.error.URLError) as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(getattr(e, 'reason', '')) or isinstance(e, ssl.SSLCertVerificationError):
            print("Info: SSL cert verification failed, retrying with relaxed SSL", file=sys.stderr)
            ctx = _ssl_fallback_ctx()
            req = urllib.request.Request(url, headers={"User-Agent": "literature-scout/1.0"})
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))

    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    if not isinstance(hits, list):
        hits = [hits] if hits else []

    results = []
    for hit in hits:
        info = hit.get("info", {})
        if not info:
            continue

        title = info.get("title", "").strip()
        venue_name = info.get("venue", "")
        year = info.get("year")
        pub_type = info.get("type", "")

        authors = info.get("authors", {}).get("author", [])
        if isinstance(authors, dict):
            authors = [authors.get("text", "")]
        else:
            authors = [a.get("text", "") if isinstance(a, dict) else str(a) for a in authors]

        # Extract URL
        link = info.get("url", "")
        ee = info.get("ee", "")  # electronic edition (usually DOI link)
        if ee:
            link = ee

        # Try to extract arXiv ID from ee URL or DOI
        arxiv_id = ""
        if "arxiv.org" in ee:
            # e.g. https://arxiv.org/abs/2502.07532
            parts = ee.split("/")
            if parts:
                arxiv_id = parts[-1].replace(".pdf", "").split("v")[0]
        elif "arxiv" in info.get("doi", "").lower():
            # e.g. DOI 10.48550/ARXIV.2502.07532
            doi = info.get("doi", "")
            m = re.search(r'arxiv\.(\d{4}\.\d{4,5})', doi, re.IGNORECASE)
            if m:
                arxiv_id = m.group(1)

        results.append({
            "title": title,
            "authors": authors[:5],
            "year": int(year) if year and str(year).isdigit() else year,
            "venue": venue_name,
            "type": pub_type,
            "arxiv_id": arxiv_id,
            "doi": info.get("doi", ""),
            "link": link,
            "source": "dblp",
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="Search DBLP")
    parser.add_argument("query", help="Search keywords")
    parser.add_argument("--max", type=int, default=15, help="Max results")
    parser.add_argument("--venue", default=None, help="Filter by venue (e.g. ICML, NeurIPS, ICLR)")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    results = search(args.query, args.max, args.venue)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
