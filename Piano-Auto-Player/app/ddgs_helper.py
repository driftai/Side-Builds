import html
import json
import re
import sys
import urllib.parse
import urllib.request


def search_ddg_direct(query: str, max_results: int = 18) -> list[dict]:
    url = "https://html.duckduckgo.com/html/"
    data = urllib.parse.urlencode({"q": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    results: list[dict] = []
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            content = response.read().decode("utf-8", errors="replace")
        blocks = content.split('class="result__body')
        for b in blocks[1:]:
            title_m = re.search(r'<a class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.I | re.S)
            if not title_m:
                continue
            href = title_m.group(1).strip()
            if "uddg=" in href:
                try:
                    href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                except Exception:
                    pass
            title = html.unescape(re.sub(r"<[^>]+>", "", title_m.group(2))).strip()
            body = ""
            body_m = re.search(r'<a class="result__snippet"[^>]*>(.*?)</a>', b, re.I | re.S)
            if body_m:
                body = html.unescape(re.sub(r"<[^>]+>", "", body_m.group(1))).strip()
            if href and title:
                results.append({"title": title, "href": href, "body": body})
            if len(results) >= max_results:
                break
    except Exception:
        pass
    return results


def main() -> int:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print("[]")
        return 0
    try:
        from ddgs import DDGS
        rows = DDGS(timeout=8).text(query, region="us-en", safesearch="moderate", max_results=18, backend="auto")
        if isinstance(rows, list) and rows:
            print(json.dumps(rows, ensure_ascii=False))
            return 0
    except Exception:
        pass
    rows = search_ddg_direct(query, max_results=18)
    print(json.dumps(rows or [], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
