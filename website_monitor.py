#!/usr/bin/env python3
"""Daily public webpage change signals for the iGuzzini UK Marketing Hub.

Checks selected public HTML only. No social network scraping, account access,
automated strategic interpretation or unsupported claims about marketing impact.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
WATCHLIST = ROOT / "monitor_sources.json"
OUTPUT = ROOT / "docs" / "site-change-monitor.json"
AGENT = "iGuzziniUK-PublicSourceMonitor/1.0 (public marketing-page checks)"
IGNORE = {"script", "style", "noscript", "svg", "iframe", "form", "nav", "footer"}


class ReadableHTML(HTMLParser):
    """Conservative server-HTML extraction; never executes page JavaScript."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.body = []
        self.main = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)

    def handle_endtag(self, tag):
        if tag in self.tags:
            index = len(self.tags) - 1 - self.tags[::-1].index(tag)
            del self.tags[index:]

    def handle_data(self, data):
        if not data.strip() or any(tag in IGNORE for tag in self.tags):
            return
        cleaned = " ".join(data.split())
        if cleaned and ("body" in self.tags or "main" in self.tags):
            self.body.append(cleaned)
            if "main" in self.tags:
                self.main.append(cleaned)


def normalized_text(html):
    parser = ReadableHTML()
    parser.feed(html)
    use = parser.main if len(" ".join(parser.main)) >= 180 else parser.body
    return re.sub(r"\s+", " ", " ".join(use)).strip()[:120000]


def readable_blocks(html_body):
    """Short visible heading/paragraph fragments for explaining detected changes."""
    matches = re.findall(
        r'<(?:h[1-4]|p)\b[^>]*>(.*?)</(?:h[1-4]|p)>',
        html_body, flags=re.I | re.S,
    )
    blocks = []
    seen = set()
    for section in matches[:350]:
        clean = " ".join(unescape(re.sub(r"<[^>]*>", " ", section)).split())
        if not 48 <= len(clean) <= 550:
            continue
        if re.search(r"^(?:cookie|privacy|accept all|newsletter signup|contact us)\b", clean, re.I):
            continue
        digest = hashlib.sha256(clean.casefold().encode("utf-8")).hexdigest()[:16]
        if digest not in seen:
            seen.add(digest)
            blocks.append((digest, clean))
        if len(blocks) >= 150:
            break
    return blocks


def check_one(source, previous):
    row = {field: source[field] for field in ("id", "brand", "url", "categories")}
    row.update(status="error", changed_in_latest_scan=False, baseline=False)
    if not row["url"].startswith("https://"):
        row.update(status="invalid", detail="Only HTTPS sources are supported")
        return row
    try:
        request = Request(row["url"], headers={
            "User-Agent": AGENT,
            "Accept": "text/html,application/xhtml+xml",
        })
        with urlopen(request, timeout=14) as response:
            if response.status != 200:
                raise ValueError("HTTP status " + str(response.status))
            ctype = response.headers.get("Content-Type", "").lower()
            if "html" not in ctype:
                raise ValueError("Source did not return HTML")
            body = response.read(900000).decode("utf-8", "replace")
        text = normalized_text(body)
        if len(text) < 130:
            raise ValueError("Too little readable server HTML to compare")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        blocks = readable_blocks(body)
        old_blocks = set(previous.get("block_hashes") or [])
        old_digest = previous.get("digest")
        changed = bool(old_digest and digest != old_digest)
        new_fragments = [value for key, value in blocks if key not in old_blocks] if old_blocks and changed else []
        snippets = [" ".join(value.split()[:18]) for value in new_fragments[:3]]
        row.update(status="ok", digest=digest, characters=len(text),
                   block_hashes=[key for key, _ in blocks], change_snippets=snippets,
                   baseline=not bool(old_digest),
                   changed_in_latest_scan=changed,
                   last_changed_at=(
                       datetime.now(timezone.utc).isoformat() if changed
                       else previous.get("last_changed_at")
                   ))
    except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
        row.update(status="error", detail=str(exc)[:160],
                   digest=previous.get("digest"),
                   last_changed_at=previous.get("last_changed_at"))
    return row


def main():
    config = json.loads(WATCHLIST.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1 or not isinstance(config.get("sources"), list):
        raise ValueError("Invalid source watchlist")
    earlier = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    previous = {row["id"]: row for row in earlier.get("sources", []) if "id" in row}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(
            lambda src: check_one(src, previous.get(src["id"], {})), config["sources"]
        ))
    counts = {
        "checked": sum(row["status"] == "ok" for row in records),
        "unavailable": sum(row["status"] != "ok" for row in records),
        "changed": sum(row["changed_in_latest_scan"] for row in records),
        "new_baselines": sum(row["baseline"] for row in records),
    }
    output = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "Selected public server-HTML text only, checked daily; "
            "changes are unreviewed signals. Social networks excluded. "
            "Some sites block automated reading or rely on JavaScript."
        ),
        "counts": counts,
        "sources": records,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Public source-monitor result:", counts)
    for row in records:
        print(row["brand"], row["status"], "changed" if row["changed_in_latest_scan"] else
              "new baseline" if row["baseline"] else "", row.get("detail", "")[:70])


if __name__ == "__main__":
    main()
