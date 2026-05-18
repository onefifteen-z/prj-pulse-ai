---
name: pulse-ai-x
description: This skill should be used when the user asks for "AI Twitter",
  "AI X signals", "AI leaders tweets", or invokes /pulse-ai-x.
  Fetches posts from selected AI leaders on X (Twitter) using a Python RSS pipeline,
  filters recent signals, detects multi-account resonance, and generates
  a Markdown report.
argument-hint: "[output-dir]"
---

---

# pulse-ai-x

X (Twitter) AI signal detection skill for the `pulse-ai` project. Tracks a
curated list of AI leaders via RSS (Nitter), processes posts using a Python
backend for filtering and deduplication, and applies LLM-based signal extraction
and resonance detection.

---

## Output directory

Default:

inbox/twitter-trending/

---

## Step 1: Compute today's date

Format:

YYYY-MM-DD.md

---

## Step 2: Check if today's report already exists

Path:

<output-dir>/<today>.md

Example:

inbox/twitter-trending/2026-05-01.md

If exists:

"Today's X AI report already exists: <path>. Re-fetch?"

Wait for confirmation before proceeding.

---

## Step 3: Fetch posts (Python preferred)

Use Python reference script to:

- Fetch RSS feeds from Nitter
- Filter posts within last 7 days
- Deduplicate
- Limit posts per account

Tracked accounts:

Core builders:

- karpathy
- sama
- ylecun
- fchollet
- rasbt
- DrJimFan
- Thom_Wolf

Aggregators:

- dair_ai

Python should output (each item):

- `user`, `text` (RSS title), `link` (Nitter URL from RSS, for traceability)
- `link_x`: **canonical post URL on X** — see **Canonical X URLs** below
- `description_html` (optional but recommended): RSS `<description>` body (often HTML with `<p>`, `<blockquote>`, `<br>`). Used to surface **golden quotes** in the report.
- `published`: ISO datetime (UTC)

Example shape:

[
{
"user": "karpathy",
"text": "This is the the quote I've been citing a lot recently.",
"link": "https://nitter.net/karpathy/status/2049907410303865030#m",
"link_x": "https://x.com/karpathy/status/2049907410303865030",
"description_html": "<p>...</p>",
"published": "2026-04-30T17:43:06+00:00"
}
]

---

## Canonical X URLs (nitter → x.com)

For every cited post in the Markdown report:

- Prefer **`https://x.com/<handle>/status/<snowflake>`** as the **primary link users click**.
- Derive it from the Nitter RSS `link` by:
  - Replacing host **`nitter.net`** (or other Nitter host) with **`x.com`**
  - Dropping trailing **`#m`** (or any fragment)
  - Keeping the **same path** (`/<user>/status/<id>`), including when the status is a **quote-tweet** or RT and the path points at the **quoted author’s** status — that is still the correct canonical X URL for that tweet.

Do **not** rewrite the numeric status id. If conversion is ambiguous, keep the Nitter URL as a secondary line (`**RSS mirror**:`) and still attempt `x.com` when the path matches `/status/`.

---

## Golden quotes (金句)

When a post (or its embedded quote) contains a short, memorable line worth preserving **verbatim**:

- Add a bullet **`Quote`** (or **`金句`**) under that signal or under **per-post references**.
- **Preserve rhythm and line breaks** from the source. If the RSS `description_html` uses HTML such as `<p>...</p>` or `<br>`, **keep that HTML** in the Markdown file so breaks stay faithful (most Markdown renderers allow safe inline HTML blocks for this).

Example (preserve HTML line breaks in the saved report; show literally in the output file):

```html
<p>you can outsource your thinking<br>
but you cannot outsource your understanding</p>
```

Guidelines:

- Prefer **1–3 tight sentences** (or one short stanza); avoid dumping the full RSS HTML unless it is the point of the signal.
- If the gold line lives inside a **blockquote** in `description_html`, extract that fragment rather than paraphrasing.
- If there is no standout line, omit **`Quote`** rather than filler.

---

## Step 4: Fallback (no Python available)

If Python is unavailable:

- Fetch RSS directly:

https://nitter.net/<username>/rss

- Take latest 5 posts per user
- Prefer posts within last 3–7 days
- Skip replies and retweets if possible

---

## Step 5: Filter posts (LLM)

Keep posts that:

- Are related to AI / LLM / models / agents
- Contain technical, product, or strategic insight
- Ignore personal or irrelevant content

---

## Step 6: Extract signal (LLM)

For each post:

Output:

{
"topic": "...",
"keywords": ["...", "..."],
"summary": "...",
"type": "technical | product | research",
"quote_html": "optional: memorable fragment, may include <p>/<br>"
}

---

## Step 7: Resonance detection

Group posts by topic similarity.

### Weight rules:

Core builders:

- karpathy = 5
- sama = 4
- ylecun = 4
- fchollet = 4
- rasbt = 4
- DrJimFan = 4
- Thom_Wolf = 4

Aggregators:

- dair_ai = 2

---

### Time decay:

- ≤ 1 day → weight × 1.0
- ≤ 3 days → weight × 0.7
- ≤ 7 days → weight × 0.4

---

### Score calculation:

score = sum(adjusted weights)

---

### Tag rules:

- score ≥ 8 → ⭐ Strong signal
- score ≥ 5 → 🔥 Emerging
- else → weak

---

## Step 8: Generate Markdown report

Format:

# X AI Pulse - YYYY-MM-DD

> Window: last 7 days
> Accounts: 8 tracked
> Signals: N total / M strong

---

## 🔥 Strong Signals

### ⭐ Topic

- **Mentioned by**: A, B, C
- **Posts on X** (canonical): https://x.com/A/status/…, https://x.com/B/status/…
- **Summary**: ...
- **Quote** (optional; preserve `<p>` / `<br>` when they carry the rhythm):

<p>…</p>

- **Why it matters**: ...

---

## 🧪 Emerging Signals

### 🔥 Topic

- **Mentioned by**: A, B
- **Posts on X**: https://x.com/…
- **Summary**: ...
- **Quote** (optional): …

---

## ⚠️ Early Signals

### Topic

- **Mentioned by**: A
- **Post on X**: https://x.com/A/status/…
- **Status**: Single-source
- **Quote** (optional): …

---

## Step 9: Save file

<output-dir>/<today>.md

Example:

inbox/twitter-trending/2026-05-01.md

---

## Step 10: Report to user

Example:

"Generated X AI signal report:
inbox/twitter-trending/2026-05-01.md
(15 signals, 4 strong)"

---

## Failure handling

- RSS fetch fails → retry once
- If one account fails → skip
- If all fail → report error, do not generate empty file

---

## Python reference (recommended)

Use Python to:

- Parse RSS (feedparser or stdlib fallback in `reference/x_fetch.py`)
- Filter by time (7 days)
- Deduplicate posts
- Limit posts per account (max 3–5)
- Emit **`link_x`** (nitter → `x.com`) and **`description_html`** when available for downstream quoting

---

## Notes

- X (Twitter) is treated as early signal source
- Signals require multi-account confirmation for high confidence
- Do NOT treat single posts as strong signals
- Nitter may be unstable; system should tolerate partial failures

---

## Relationship with pulse-ai

X is the early-signal desk. Callable standalone via `/pulse-ai-x` or as part
of `/pulse-ai` (parent orchestrator: fetch all desks, build site, publish).

Sibling skills: `pulse-ai-github`, `pulse-ai-hn`, `pulse-ai`.
