#!/usr/bin/env python3
"""Public first-party marketing activity discoveries for V93.

Collects visible named links from official site news/event/press pages. These
are source discoveries, not inferred strategies, social media monitoring or
evidence of when an activity occurred. First-seen dates are collection dates.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import html
import json
import re
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "marketing-activity.json"
CONFIG = ROOT / "activity_sources.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; iGuzziniUK-PublicResearch/1.0)",
    "Accept": "text/html,application/xhtml+xml",
}
SKIP = re.compile(
    r"^(?:home|news|press|events?|view|discover|read more|find out more|"
    r"learn more|more|details?|next|previous|back|downloads?|"
    r"en|english|see all|load more|overview|products|projects|"
    r"contact|about|subscribe|privacy|cookie|sign in|search)$", re.I,
)
UK = re.compile(r"\b(?:UK|United Kingdom|London|British|Britain|England|"
                r"Scotland|Wales|Birmingham|Manchester|Liverpool|Oxford|"
                r"Clerkenwell|Glasgow|Leeds|Bristol|Surrey)\b", re.I)
PATTERNS = {
    "Events": r"\bevent\b|exhib|conference|festival|design week|"
              r"architect.?work|clerk|light ?26|workshop|cpd|"
              r"pavilion|orgatec|euroshop|networking|webinar|showroom",
    "Content": r"case stud|project|guide|brochure|catalog|lookbook|"
               r"insights|story|article|report|research|publication|"
               r"download|white ?paper|interview|university|academy|"
               r"museum|library|heritage|architecture",
    "Messaging": r"launch|introduc|reveal|new |award|certif|"
                 r"innovation|sustainab|circular|collaborat|partner|"
                 r"campaign|future|strategy|product|collection|design|"
                 r"social impact|technology",
}


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a" and self.active is None:
            properties = dict(attrs)
            self.active = {"href": properties.get("href", ""), "text": []}
        elif tag == "img" and self.active is not None:
            pass

    def handle_data(self, data):
        if self.active is not None:
            self.active["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.active is not None:
            self.links.append((
                self.active["href"],
                " ".join(" ".join(self.active["text"]).split())
            ))
            self.active = None


def good_link(link, source):
    host = (urlsplit(link).hostname or "").lower()
    allowed = source["domain"].lower()
    return (
        link.startswith("https://")
        and (host == allowed or host.endswith("." + allowed))
        and len(urlsplit(link).path) > 12
        and any(part in urlsplit(link).path.lower() for part in source["paths"])
        and not re.search(r"\.(?:pdf|zip|docx|xlsx|jpg|jpeg|webp|png)$", link, re.I)
    )


def categories(title, link):
    combined = title + " " + link.split("/")[-1].replace("-", " ")
    found = [kind for kind, pattern in PATTERNS.items() if re.search(pattern, combined, re.I)]
    return found or ["Content"]


EXCLUDED_WORDS = {
    "iguzzini", "erco", "fagerhult", "zumtobel", "xal", "trilux",
    "deltalight", "delta", "light", "news", "event", "events",
    "press", "release", "company", "insights", "about", "more",
    "from", "this", "that", "with", "find", "read", "view", "the",
    "and", "new", "for", "2026", "2025", "2024",
}


def clean_title(title):
    title = re.sub(r"^(?:Press Release|Insights|Inspirations|General|Events)\s+", "", title, flags=re.I)
    title = re.sub(r"^Find out more\s*about\s*", "", title, flags=re.I)
    title = re.sub(r"^Top stories\s+", "", title, flags=re.I)
    title = re.sub(r"\s+Read More(?:\s.*)?$", "", title, flags=re.I)
    title = re.sub(r"\s+\d{1,2}[. ]\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}.*$", "", title, flags=re.I)
    title = re.sub(r"\s+\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\s+\d{4}\s*\|\s*NEWS ARTICLE.*$", "", title, flags=re.I)
    return title.strip(" .|-")[:160]


def listing_publication_date(label):
    # Dates on official listing cards, not dates guessed from URL paths.
    pattern = r"\b(\d{1,2})[.\s]+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[.,\s]+(20\d{2})\b"
    match = re.search(pattern, label, re.I)
    if not match:
        return None
    months = dict(jan=1,feb=2,mar=3,apr=4,may=5,jun=6,jul=7,aug=8,sep=9,oct=10,nov=11,dec=12)
    try:
        return datetime(int(match[3]), months[match[2][:3].lower()], int(match[1])).date().isoformat()
    except (ValueError, TypeError):
        return None


def matching_title_and_url(title, link):
    # Avoid headline/link mismatches caused by nested anchors or site menus.
    slug = unquote(urlsplit(link).path).strip("/").split("/")[-1]
    words = lambda t: {w for w in re.findall(r"[a-z0-9]{4,}", t.lower()) if w not in EXCLUDED_WORDS}
    title_words, slug_words = words(title), words(slug)
    if title_words and slug_words and not title_words.intersection(slug_words):
        return False
    # Filter obviously old archives from first-time discovery; never label 2024 as new in 2026.
    if re.search(r"/20(?:1\d|2[0-5])/", urlsplit(link).path):
        return False
    if re.match(r"^(?:20(?:1\d|2[0-5])|[0-3]?\d[./-][01]?\d[./-]20(?:1\d|2[0-5]))\b", title):
        return False
    if re.search(r"\b20(?:1\d|2[0-5])\b", title) and not re.search(r"\b2026\b", title):
        return False
    return True


def extract(page, source, day):
    parser = Links()
    parser.feed(page)
    best = {}
    for href, label in parser.links:
        title = html.unescape(re.sub(r"\s+", " ", label)).strip()
        if not 17 <= len(title) <= 200 or SKIP.fullmatch(title):
            continue
        target = urljoin(source["url"], href).split("#", 1)[0]
        if not good_link(target, source):
            continue
        title = clean_title(title)
        if not 15 <= len(title) <= 160 or not matching_title_and_url(title, target):
            continue
        if re.search(r"\b(patent proceedings|leading employer 2025|light25|light 25)\b", title, re.I):
            continue
        if re.search(r"\b(privacy|cookies|careers?|login|imprint|"
                     r"terms and conditions|all news|product overview)\b", title, re.I):
            continue
        key = hashlib.sha256((source["brand"] + "|" + target).encode()).hexdigest()[:20]
        item = {
            "id": key,
            "brand": source["brand"],
            "title": title,
            "summary": "",
            "category": categories(title, target)[0],
            "categories": categories(title, target),
            "source_url": target,
            "source_name": source["name"],
            "source_type": "official_website",
            "scope": "UK mentioned" if UK.search(title) else source["scope"],
            "first_seen": day,
            "published_at": listing_publication_date(label),
            "date_type": "published" if listing_publication_date(label) else "first_seen",
            "review_status": "source_discovery",
        }
        old = best.get(key)
        if not old or len(title) > len(old["title"]):
            best[key] = item
    return list(best.values())


def fetch_source(source, day):
    try:
        req = Request(source["url"], headers=HEADERS)
        with urlopen(req, timeout=15) as response:
            ctype = response.headers.get("Content-Type", "").lower()
            if "html" not in ctype:
                raise ValueError("Expected an HTML listing")
            raw = response.read(1_200_000)
        discovered = extract(raw.decode("utf-8", "replace"), source, day)
        return source, discovered[:85], {
            "brand": source["brand"], "name": source["name"],
            "url": source["url"], "status": "ok",
            "items_found": len(discovered),
        }
    except Exception as exc:
        return source, [], {
            "brand": source["brand"], "name": source["name"],
            "url": source["url"], "status": "unavailable",
            "detail": type(exc).__name__ + ": " + str(exc)[:110],
        }


def main():
    day = datetime.now(timezone.utc).date().isoformat()
    sources = json.loads(CONFIG.read_text(encoding="utf-8"))["sources"]
    old = {}
    if OUT.exists():
        try:
            old = {r["id"]: r for r in json.loads(OUT.read_text(encoding="utf-8")).get("records", [])}
        except (ValueError, KeyError):
            old = {}
    status = []
    seen = set()
    counts = {"checked_sources": 0, "unavailable_sources": 0, "newly_seen": 0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda src: fetch_source(src, day), sources))
    for src, discovered, health in results:
        status.append(health)
        counts["checked_sources" if health["status"] == "ok" else "unavailable_sources"] += 1
        for item in discovered:
            ident = item["id"]
            seen.add(ident)
            if ident not in old:
                old[ident] = item
                counts["newly_seen"] += 1
            else:
                previous = old[ident]
                previous["title"] = item["title"]
                previous["categories"] = item["categories"]
                previous["category"] = item["category"]
                previous["scope"] = item["scope"]
                if item.get("published_at") and not previous.get("published_at"):
                    previous["published_at"] = item["published_at"]
                    previous["date_type"] = "published"
    # Preserve history for 180 days, even when a source temporarily fails.
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=180)).isoformat()
    kept = [r for r in old.values() if r.get("first_seen", "") >= cutoff and not re.search(r"\b(patent proceedings|light25|light 25)\b", r.get("title", ""), re.I) and (r.get("origin") == "editorial_seed" or matching_title_and_url(r.get("title",""), r.get("source_url","")))]
    # Collapse duplicates when an editorially checked record and a scraped link share a URL.
    preferred = {}
    for row in kept:
        identity = (row["brand"], row["source_url"].rstrip("/").lower())
        previous = preferred.get(identity)
        if not previous or (row.get("origin") == "editorial_seed" and previous.get("origin") != "editorial_seed"):
            preferred[identity] = row
    kept = list(preferred.values())
    kept.sort(key=lambda r: (r["first_seen"], r["brand"], r["title"]), reverse=True)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "description": (
            "Direct links discovered on official public news, event and press pages. "
            "First-seen date is when this system noticed a link, NOT a publication or event date. "
            "New links may be older publications. Nothing here is an AI-generated finding."
        ),
        "counts": {**counts, "total_retained": min(len(kept), 900)},
        "source_status": status,
        "records": kept[:900],
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Marketing activity:", payload["counts"])
    for item in status:
        print(item["brand"], item["name"], item["status"], item.get("items_found", item.get("detail", "")))


if __name__ == "__main__":
    main()
