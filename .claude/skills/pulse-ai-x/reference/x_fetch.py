"""Fetch tracked accounts from Nitter RSS (pulse-ai-x reference).

Uses feedparser when installed; otherwise falls back to urllib + ElementTree.
Retries each feed once on failure; dedupes by link across accounts.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

MAX_DESCRIPTION_HTML = 16000

ACCOUNTS = [
    "karpathy",
    "sama",
    "ylecun",
    "fchollet",
    "rasbt",
    "DrJimFan",
    "Thom_Wolf",
    "dair_ai",
]

USER_AGENT = "Mozilla/5.0 (compatible; PulseAI/1.0)"
_NITTER = "https://nitter.net"


def nitter_to_x(url: str) -> str:
    """Map Nitter or twitter.com status URL to https://x.com/.../status/<id> (no fragment)."""
    if not url:
        return url
    base = url.split("#", 1)[0]
    p = urlparse(base)
    host = p.netloc.lower()
    path = p.path or ""

    if "nitter." in host and "/status/" in path:
        return f"https://x.com{path}"
    if host in ("twitter.com", "www.twitter.com", "mobile.twitter.com"):
        return f"https://x.com{path}"
    if host in ("x.com", "www.x.com"):
        return f"https://x.com{path}"
    return base


def _truncate_html(s: str, max_len: int = MAX_DESCRIPTION_HTML) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def _rss_item_description_html(elem: ET.Element | None) -> str:
    """Rebuild RSS item description inner HTML (keeps <p>, <br>, blockquotes)."""
    if elem is None:
        return ""
    if not list(elem):
        return (elem.text or "").strip()

    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(ET.tostring(child, encoding="unicode"))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _should_skip_title(title: str, *, skip_replies: bool, include_retweets: bool) -> bool:
    t = title.strip()
    if skip_replies and re.match(r"^R to @", t, re.I):
        return True
    if not include_retweets and re.match(r"^RT by @", t, re.I):
        return True
    return False


def _parse_rss_items(
    xml_bytes: bytes,
    user: str,
    cutoff: datetime,
    *,
    max_per_account: int,
    skip_replies: bool,
    include_retweets: bool,
) -> list[dict[str, str]]:
    root = ET.fromstring(xml_bytes)
    rows: list[dict[str, str]] = []

    for el in root.iter():
        if _strip_ns(el.tag) != "item":
            continue
        title_el = link_el = pub_el = desc_el = None
        for child in el:
            tag = _strip_ns(child.tag)
            if tag == "title":
                title_el = child
            elif tag == "link":
                link_el = child
            elif tag == "pubDate":
                pub_el = child
            elif tag == "description":
                desc_el = child

        title = _text(title_el) or "(no title)"
        link = _text(link_el)
        pub_raw = _text(pub_el)
        if not link:
            continue
        if _should_skip_title(title, skip_replies=skip_replies, include_retweets=include_retweets):
            continue

        try:
            dt = parsedate_to_datetime(pub_raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue

        if dt < cutoff:
            continue

        desc_html = _truncate_html(_rss_item_description_html(desc_el))
        rows.append(
            {
                "user": user,
                "text": title,
                "link": link,
                "link_x": nitter_to_x(link),
                "description_html": desc_html,
                "published": dt.isoformat(),
            }
        )

    rows.sort(key=lambda r: r["published"], reverse=True)
    return rows[:max_per_account]


def _fetch_user_stdlib(
    user: str,
    cutoff: datetime,
    *,
    max_per_account: int,
    max_entries_scan: int,
    skip_replies: bool,
    include_retweets: bool,
) -> list[dict[str, str]]:
    url = f"{_NITTER}/{user}/rss"
    last_err: BaseException | None = None
    for attempt in range(2):
        try:
            data = _http_get(url)
            # Scan more items than we keep so filtering by date still fills the cap.
            raw = _parse_rss_items(
                data,
                user,
                cutoff,
                max_per_account=max_entries_scan,
                skip_replies=skip_replies,
                include_retweets=include_retweets,
            )
            return raw[:max_per_account]
        except (urllib.error.URLError, OSError, ET.ParseError) as e:
            last_err = e
            if attempt == 0:
                time.sleep(1.2)
    print(f"# skip {user}: {last_err}", flush=True)
    return []


def _entry_datetime(entry: Any) -> datetime | None:
    if getattr(entry, "published_parsed", None):
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return None


def _fetch_user_feedparser(
    user: str,
    cutoff: datetime,
    *,
    max_per_account: int,
    max_entries_scan: int,
    skip_replies: bool,
    include_retweets: bool,
) -> list[dict[str, str]]:
    import feedparser

    url = f"{_NITTER}/{user}/rss"
    last_err: BaseException | None = None

    for attempt in range(2):
        rows: list[dict[str, str]] = []
        try:
            feed = feedparser.parse(url)
            if not feed.entries and getattr(feed, "bozo_exception", None):
                raise feed.bozo_exception  # type: ignore[misc]

            for entry in feed.entries[:max_entries_scan]:
                title = (entry.get("title") or "").strip() or "(no title)"
                link = (entry.get("link") or "").strip()
                if not link:
                    continue
                if _should_skip_title(title, skip_replies=skip_replies, include_retweets=include_retweets):
                    continue

                dt = _entry_datetime(entry)
                if dt is None:
                    continue
                if dt < cutoff:
                    continue

                raw_desc = (entry.get("description") or entry.get("summary") or "").strip()
                rows.append(
                    {
                        "user": user,
                        "text": title,
                        "link": link,
                        "link_x": nitter_to_x(link),
                        "description_html": _truncate_html(raw_desc),
                        "published": dt.isoformat(),
                    }
                )

            rows.sort(key=lambda r: r["published"], reverse=True)
            return rows[:max_per_account]
        except Exception as e:
            last_err = e
            if attempt == 0:
                time.sleep(1.2)

    print(f"# skip {user}: {last_err}", flush=True)
    return []


def fetch_tweets(
    days: int = 7,
    *,
    max_per_account: int = 5,
    max_entries_scan: int = 15,
    skip_replies: bool = True,
    include_retweets: bool = True,
    dedupe_by_link: bool = True,
    delay_s: float = 0.35,
) -> list[dict[str, str]]:
    """Return recent posts newer than ``days`` from each tracked account.

    Each dict: user, text, link, link_x, description_html, published (ISO-8601 UTC).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    fetch_one = (
        _fetch_user_feedparser
        if importlib.util.find_spec("feedparser") is not None
        else _fetch_user_stdlib
    )

    all_rows: list[dict[str, str]] = []
    for user in ACCOUNTS:
        all_rows.extend(
            fetch_one(
                user,
                cutoff,
                max_per_account=max_per_account,
                max_entries_scan=max_entries_scan,
                skip_replies=skip_replies,
                include_retweets=include_retweets,
            )
        )
        if delay_s > 0:
            time.sleep(delay_s)

    if not dedupe_by_link:
        all_rows.sort(key=lambda r: r["published"], reverse=True)
        return all_rows

    by_link: dict[str, dict[str, str]] = {}
    for row in all_rows:
        by_link.setdefault(row["link"], row)
    out = sorted(by_link.values(), key=lambda r: r["published"], reverse=True)
    return out


if __name__ == "__main__":
    rows = fetch_tweets()
    json.dump(rows, sys.stdout, indent=2)
