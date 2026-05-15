"""Pulse — static site + RSS generator for prj-pulse-ai.

Reads daily reports from inbox/{twitter,hn,github}-trending/*.md
and renders them to docs/ as a small editorial-style site with
a homepage, per-source archives, single-post pages, and four RSS feeds
(combined + per-source).

Dependencies: markdown, jinja2 (see build/requirements.txt).
"""
from __future__ import annotations

import datetime as dt
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

import markdown as md_lib
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "inbox"
OUT = ROOT / "docs"
TEMPLATES = ROOT / "build" / "templates"
ASSETS = ROOT / "build" / "assets"

SITE_URL = "https://onefifteen-z.github.io/prj-pulse-ai"
SITE_TITLE = "Pulse"
SITE_TAGLINE = "Daily AI signals from X, Hacker News & GitHub"
SITE_AUTHOR = "onefifteen-z"
PUBLISH_TZ = dt.timezone(dt.timedelta(hours=9))  # JST
PUBLISH_TIME = dt.time(9, 0, 0)
GENERATED_AT = dt.datetime.now(tz=PUBLISH_TZ)

SOURCES = {
    "twitter-trending": {
        "slug": "x",
        "label": "X",
        "desk": "X DESK",
        "accent": "#5cc2ff",
        "blurb": "Early signals from researcher & founder posts.",
        "icon_text": "X",
        "summary_word": "signals",
    },
    "hn-trending": {
        "slug": "hn",
        "label": "Hacker News",
        "desk": "HACKERS DESK",
        "accent": "#ff7a3c",
        "blurb": "Discussion signals from the front page.",
        "icon_text": "HN",
        "summary_word": "items",
    },
    "github-trending": {
        "slug": "gh",
        "label": "GitHub",
        "desk": "GIT DESK",
        "accent": "#b388ff",
        "blurb": "Implementation signals from trending repos.",
        "icon_text": "GH",
        "summary_word": "repos",
    },
}

H1_RE = re.compile(r"^# (.+)$", re.MULTILINE)
H2_RE = re.compile(r"^## (.+)$", re.MULTILINE)
H3_RE = re.compile(r"^### (.+)$", re.MULTILINE)
META_RE = re.compile(r"^> (.+)$", re.MULTILINE)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

# Pictographic / dingbat / variation-selector ranges. Used to strip the
# decorative emoji that often prefix our `### ⭐ …` headings, while keeping
# legitimate punctuation (`"`, `'`, `(`, digits, `—`) intact.
_EMOJI_PREFIX = re.compile(
    r"^[\s\u2300-\u23ff\u2600-\u27bf\u2b00-\u2bff\ufe00-\ufe0f"
    r"\U0001f000-\U0001fbff]+"
)


def _strip_emoji_prefix(s: str) -> str:
    return _EMOJI_PREFIX.sub("", s).strip()


def parse_post(path: Path, source: dict[str, Any]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")

    title_match = H1_RE.search(text)
    raw_title = title_match.group(1).strip() if title_match else path.stem
    body_md = H1_RE.sub("", text, count=1).lstrip("\n")

    # Strip the leading meta blockquote (`> Window: ...` etc) — we already
    # render it as the styled `post__lede`, so leaving it in the body would
    # duplicate the content.
    body_md = re.sub(r"\A(?:>[^\n]*\n)+\s*(?:---\s*\n+)?", "", body_md)

    # Tag bare inline <p>...</p> quote blocks so CSS can pull-quote them.
    # In our reports these always start at column 0 on their own line.
    body_md = re.sub(r"^<p>", '<p class="pulse-quote">', body_md, flags=re.MULTILINE)

    date_match = DATE_RE.search(path.stem)
    date_iso = date_match.group(1) if date_match else "1970-01-01"
    date = dt.date.fromisoformat(date_iso)
    published = dt.datetime.combine(date, PUBLISH_TIME, tzinfo=PUBLISH_TZ)

    meta_lines = [m.group(1).strip() for m in META_RE.finditer(text)]

    h3_titles = [_strip_emoji_prefix(m.group(1)) for m in H3_RE.finditer(text)]
    h3_titles = [t for t in h3_titles if t][:3]

    md = md_lib.Markdown(
        extensions=["fenced_code", "tables", "attr_list", "toc", "sane_lists"],
        extension_configs={"toc": {"toc_depth": "2-3", "anchorlink": False, "permalink": False}},
        output_format="html5",
    )
    html = md.convert(body_md)
    toc = getattr(md, "toc_tokens", []) or []

    rel_url = f"/{source['slug']}/{path.stem}.html"
    abs_url = SITE_URL + rel_url

    return {
        "title": raw_title,
        "date": date,
        "iso_date": date.isoformat(),
        "human_date": date.strftime("%A · %b %d, %Y"),
        "published": published,
        "meta_lines": meta_lines,
        "teaser_headings": h3_titles,
        "html": html,
        "toc": toc,
        "stem": path.stem,
        "source": source,
        "url": abs_url,
        "rel_url": rel_url,
    }


def collect_posts() -> dict[str, list[dict[str, Any]]]:
    by_source: dict[str, list[dict[str, Any]]] = {}
    for folder, source in SOURCES.items():
        files = sorted((SRC / folder).glob("*.md"))
        posts = [parse_post(p, source) for p in files]
        posts.sort(key=lambda p: p["date"], reverse=True)
        by_source[source["slug"]] = posts
    return by_source


def write_html(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def render_site(by_source: dict[str, list[dict[str, Any]]]) -> None:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(
        site_url=SITE_URL,
        site_title=SITE_TITLE,
        site_tagline=SITE_TAGLINE,
        sources=list(SOURCES.values()),
        generated_at=GENERATED_AT,
    )

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    for asset in ASSETS.iterdir():
        target = OUT / asset.name
        if asset.is_dir():
            shutil.copytree(asset, target)
        else:
            shutil.copy(asset, target)

    post_tpl = env.get_template("post.html")
    index_tpl = env.get_template("index.html")
    home_tpl = env.get_template("home.html")

    for slug, posts in by_source.items():
        if not posts:
            continue
        for i, post in enumerate(posts):
            post["prev"] = posts[i + 1] if i + 1 < len(posts) else None
            post["next"] = posts[i - 1] if i - 1 >= 0 else None
        for post in posts:
            html = post_tpl.render(post=post)
            write_html(OUT / slug / f"{post['stem']}.html", html)

        write_html(
            OUT / slug / "index.html",
            index_tpl.render(
                posts=posts,
                source=posts[0]["source"],
                feed_url=f"{SITE_URL}/{slug}/feed.xml",
            ),
        )

    all_posts = [p for posts in by_source.values() for p in posts]
    all_posts.sort(key=lambda p: p["date"], reverse=True)
    write_html(
        OUT / "index.html",
        home_tpl.render(by_source=by_source, recent=all_posts[:12]),
    )

    write_feed(OUT / "feed.xml", all_posts, label="All sources")
    for slug, posts in by_source.items():
        if posts:
            write_feed(
                OUT / slug / "feed.xml",
                posts,
                label=posts[0]["source"]["label"],
                slug=slug,
            )


def feed_description(post: dict[str, Any]) -> str:
    pieces = []
    if post["meta_lines"]:
        pieces.append(" — ".join(post["meta_lines"][:2]))
    if post["teaser_headings"]:
        pieces.append(" · ".join(f"“{h}”" for h in post["teaser_headings"]))
    return "  ".join(pieces) or post["title"]


ET.register_namespace("atom", "http://www.w3.org/2005/Atom")
ET.register_namespace("dc", "http://purl.org/dc/elements/1.1/")


def write_feed(
    path: Path,
    posts: list[dict[str, Any]],
    label: str,
    slug: str | None = None,
    limit: int = 50,
) -> None:
    rss = ET.Element("rss", attrib={"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = f"Pulse · {label}"
    site_link = SITE_URL if slug is None else f"{SITE_URL}/{slug}/"
    ET.SubElement(ch, "link").text = site_link
    ET.SubElement(ch, "description").text = (
        f"Daily AI signal reports — {label}." if slug else SITE_TAGLINE
    )
    ET.SubElement(ch, "language").text = "en"
    ET.SubElement(ch, "lastBuildDate").text = format_datetime(GENERATED_AT)
    ET.SubElement(ch, "generator").text = "pulse-build"
    feed_self = path.relative_to(OUT).as_posix()
    ET.SubElement(
        ch,
        "{http://www.w3.org/2005/Atom}link",
        attrib={
            "href": f"{SITE_URL}/{feed_self}",
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    for post in posts[:limit]:
        item = ET.SubElement(ch, "item")
        ET.SubElement(item, "title").text = post["title"]
        ET.SubElement(item, "link").text = post["url"]
        guid = ET.SubElement(item, "guid", attrib={"isPermaLink": "true"})
        guid.text = post["url"]
        ET.SubElement(item, "pubDate").text = format_datetime(post["published"])
        ET.SubElement(item, "category").text = post["source"]["label"]
        ET.SubElement(item, "{http://purl.org/dc/elements/1.1/}creator").text = SITE_AUTHOR
        ET.SubElement(item, "description").text = feed_description(post)

    ET.indent(rss, space="  ")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b'<?xml version="1.0" encoding="utf-8"?>\n'
        + ET.tostring(rss, encoding="utf-8")
    )


def main() -> int:
    if not SRC.exists():
        print(f"missing source dir: {SRC}", file=sys.stderr)
        return 1
    posts = collect_posts()
    total = sum(len(v) for v in posts.values())
    if total == 0:
        print("no markdown files found in inbox/*", file=sys.stderr)
        return 1
    render_site(posts)
    print(f"built {total} posts → {OUT.relative_to(ROOT)}")
    for slug, ps in posts.items():
        print(f"  {slug}: {len(ps)} posts (latest {ps[0]['stem']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
