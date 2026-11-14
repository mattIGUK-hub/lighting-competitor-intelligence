#!/usr/bin/env python3
"""Collect PUBLIC RSS discoveries for the iGuzzini UK competitor research pilot.

No paid APIs. Discovery results are unverified and must be checked by a human.
This script does not authenticate to or scrape social networks or private sites.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import json
import re
import sys
import xml.etree.ElementTree as ET

BRANDS = {"ERCO", "Fagerhult", "Zumtobel", "XAL", "TRILUX", "Delta Light"}
CATEGORIES = [
    ("Sustainability", r"sustainab|circular|recycl|emission|carbon|ecovadis|remanufactur|epd"),
    ("Events", r"event|exhibition|design week|showroom|conference|webinar|expo"),
    ("Partnerships", r"partnership|collaborat|sponsor|agreement"),
    ("Projects", r"project|museum|school|university|hotel|library|heritage|workplace"),
    ("Products", r"product|luminaire|spotlight|lighting system|led|innovation|collection|launch"),
    ("Business", r"acquisition|annual report|executive|revenue|appointment"),
]
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "docs" / "intelligence.json"
SOURCES = ROOT / "sources.json"


def classify(text):
    for category, pattern in CATEGORIES:
        if re.search(pattern, text, re.I):
            return category
    return "Other"


def region(text):
    return "UK" if re.search(r"\b(?:united kingdom|britain|british|london|england|scotland|wales|uk)\b", text, re.I) else "Unconfirmed"


def is_safe_link(url, domain):
    try:
        parsed = urlsplit(url.strip())
        host = (parsed.hostname or "").lower()
        domain = domain.lower()
        return parsed.scheme == "https" and (host == domain or host.endswith("." + domain))
    except ValueError:
        return False


def parse_date(date_text):
    try:
        value = parsedate_to_datetime(date_text)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).date()
    except (TypeError, ValueError, OverflowError):
        return None


def matches_brand(brand, text):
    aliases = {
        "ERCO": r"\berco\b",
        "Fagerhult": r"\bfagerhult\b",
        "Zumtobel": r"\bzumtobel\b",
        "XAL": r"\bxal\b",
        "TRILUX": r"\btrilux\b",
        "Delta Light": r"\bdelta[\s-]?light\b",
    }
    return bool(re.search(aliases[brand], text, re.I))


def rss_records(xml_bytes, source, today):
    root = ET.fromstring(xml_bytes)
    if root.tag not in ("rss", "{http://www.w3.org/2005/Atom}feed"):
        raise ValueError("Not an RSS or Atom feed")
    atom = "{http://www.w3.org/2005/Atom}"
    result = []
    if root.tag == "rss":
        entries = []
        for item in root.findall(".//item"):
            entries.append({
                "title": item.findtext("title", ""),
                "url": item.findtext("link", ""),
                "date": item.findtext("pubDate", ""),
                "description": item.findtext("description", ""),
            })
    else:
        entries = []
        for item in root.findall(atom + "entry"):
            link = item.find(atom + "link")
            entries.append({
                "title": item.findtext(atom + "title", ""),
                "url": link.get("href", "") if link is not None else "",
                "date": item.findtext(atom + "published", "") or item.findtext(atom + "updated", ""),
                "description": item.findtext(atom + "summary", ""),
            })
    for item in entries:
        title = " ".join(unescape(item["title"] or "").split())[:220]
        url = (item["url"] or "").strip()
        if not title or not is_safe_link(url, source["expected_domain"]):
            continue
        published = parse_date(item["date"])
        if published is None:
            try:
                published = datetime.fromisoformat(item["date"].replace("Z", "+00:00")).date()
            except (ValueError, AttributeError):
                continue
        if not today - timedelta(days=400) <= published <= today + timedelta(days=1):
            continue
        summary = " ".join(unescape(re.sub(r"<[^>]+>", " ", item["description"] or "")).split())[:360]
        context = title + " " + summary
        company = source["competitor"]
        key = sha256((company.lower() + "|" + url.split("#")[0]).encode()).hexdigest()[:16]
        result.append({
            "id": key, "competitor": company, "headline": title, "summary": summary,
            "published_at": published.isoformat(), "date_precision": "day",
            "source_url": url, "source_name": source["name"],
            "category": classify(context), "geography": region(context),
            "origin": "automated_discovery", "verification": "needs_review",
            "brand_match": matches_brand(company, context),
        })
    return result


def load_json(path, fallback):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def fetch_xml(url):
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; public-lighting-research-pilot/0.1)",
        "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.2",
    })
    with urlopen(request, timeout=20) as response:
        data = response.read(1_500_001)
    if len(data) > 1_500_000:
        raise ValueError("Response too large")
    return data


def main():
    now = datetime.now(timezone.utc)
    today = now.date()
    config = load_json(SOURCES, {"sources": []})
    existing = load_json(DATA, {"records": []})
    old = {x["id"]: x for x in existing.get("records", []) if isinstance(x, dict) and x.get("id")}
    retained = len(old)
    statuses = []
    found = added = failures = 0
    for source in config.get("sources", []):
        name = source.get("competitor", "")
        if name not in BRANDS:
            statuses.append({"competitor": name, "status": "error", "detail": "Unknown competitor"})
            failures += 1
            continue
        try:
            parsed = urlsplit(source["url"])
            if not is_safe_link(source["url"], source["expected_domain"]):
                raise ValueError("Untrusted source URL")
            records = rss_records(fetch_xml(source["url"]), source, today)
            found += len(records)
            for record in records:
                if record["id"] not in old:
                    record["collected_at"] = today.isoformat()
                    old[record["id"]] = record
                    added += 1
            statuses.append({"competitor": name, "status": "ok", "items_discovered": len(records)})
        except Exception as exc:
            failures += 1
            statuses.append({"competitor": name, "status": "error", "detail": type(exc).__name__ + ": " + str(exc)[:120]})
    records = sorted(old.values(), key=lambda x: (x.get("published_at") or "", x.get("competitor") or ""), reverse=True)[:1000]
    result = {
        "schema_version": 1, "generated_at": now.isoformat(timespec="seconds"),
        "feed_type": "public_research_discovery",
        "note": "Automatically discovered public headlines. Every record requires source and claim verification.",
        "source_status": statuses,
        "counts": {"found": found, "added": added, "retained": retained, "failures": failures},
        "records": records,
    }
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Collection result:", json.dumps(result["counts"]))
    for status in statuses:
        print(status["competitor"] + ": " + status["status"] + " " + str(status.get("items_discovered", status.get("detail", ""))))
    if failures == len(config.get("sources", [])):
        print("WARNING: All sources failed; no fresh research discovered.", file=sys.stderr)


if __name__ == "__main__":
    main()
