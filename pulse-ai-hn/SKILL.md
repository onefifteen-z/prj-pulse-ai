---
name: pulse-ai-hn
description: This skill should be used when the user asks for "Hacker News AI",
  "HN AI trends", "AI discussions on Hacker News", or invokes /pulse-ai-hn.
  Fetches top Hacker News stories, filters AI-related items, summarizes
  discussions, and generates a Markdown report.
argument-hint: "[output-dir]"
---

# pulse-ai-hn

Hacker News AI signal aggregation skill for the `pulse-ai` project. Fetches
top stories from Hacker News, filters AI-related items, extracts lightweight
comment discussions, and generates a Markdown intelligence brief.

---

## When to use this skill

- User invokes `/pulse-ai-hn`
- User asks for "HN AI", "Hacker News AI trends", "AI discussions"
- Called by parent `pulse-ai` skill

---

## Output directory

Default:

```
inbox/hn-trending/
```

Custom:

```
/pulse-ai-hn reports/hn
```

---

## Step 1: Compute today's date

Use current date (NOT Monday like GitHub skill).

Format:

```
YYYY-MM-DD.md
```

Example:

```
2026-05-01.md
```

---

## Step 2: Check if today's report already exists

Path:

```
<output-dir>/<today>.md
```

Example:

```
inbox/hn-trending/2026-05-01.md
```

If exists:

👉 Reply:

```
Today's Hacker News report already exists:
<path>. Re-fetch?
```

Wait for confirmation ("re-fetch", "overwrite") before proceeding.

---

## Step 3: Fetch top stories

### Preferred (if Python available)

Use reference script to fetch pre-filtered data.

### Otherwise (pure skill)

Fetch:

```
https://hacker-news.firebaseio.com/v0/topstories.json
```

- Take first ~40 IDs (to allow filtering)

Then fetch each:

```
https://hacker-news.firebaseio.com/v0/item/<id>.json
```

---

## Step 4: Filter items

Keep items that:

- type == "story"
- Title is AI-related (keywords like: AI, GPT, LLM, agent, model, diffusion)
- Prefer items within last 24–48 hours (based on "time")
- Keep top 20 items after filtering

Do NOT strictly discard older items if not enough results.

---

## Step 5: Fetch comments (lightweight)

For each item:

- Use `kids` field
- Fetch up to 3–5 comments
- Extract only `text`
- Ignore deleted / empty comments
- Strip HTML tags

---

## Step 6: Summarize (LLM)

For each item:

Input:

- title
- url
- points (score)
- comment count (descendants)
- comments (cleaned text)

Tasks:

1. Write a one-sentence summary
2. Extract 2–3 key discussion points
3. Explain why this matters in AI context

Output JSON:

```
{
  "summary": "...",
  "key_points": ["...", "..."],
  "why_it_matters": "..."
}
```

---

## Step 7: Sort items

Sort by:

- points (descending)

---

## Step 8: Generate Markdown report

Format:

```markdown
# Hacker News AI Pulse - YYYY-MM-DD

> Fetched at: YYYY-MM-DD HH:MM
> Items: N

---

## 💬 Highlights

### 1. Title

- **Points**: 532
- **Comments**: 120
- **URL**: https://...

**Summary**
...

**Key discussion**

- ...
- ...

**Why it matters**
...

---
```

---

## Step 9: Save file

Write to:

```
<output-dir>/<today>.md
```

Example:

```
inbox/hn-trending/2026-05-01.md
```

---

## Step 10: Report to user

Return:

- Number of items processed
- Output path

Example:

```
Generated Hacker News AI report:
inbox/hn-trending/2026-05-01.md (12 items)
```

---

## Failure handling

- API failure:
  - Retry once
  - If still fails: report error, do NOT generate empty file

- Parsed items too few (<3):
  - Treat as failure
  - Inform user: possible API or filtering issue

- Comments unavailable:
  - Still generate report (skip discussion section for that item)

---

## Rate limiting

- Avoid repeated fetch within short time
- If re-fetch requested, wait briefly before retry

---

## Python reference (optional)

If available, prefer using Python script (reference/hn_fetch.py) to:

- Handle time filtering precisely
- Clean HTML reliably
- Limit comment size
- Reduce token usage

Otherwise fallback to pure skill implementation.

---

## Notes

- HN API provides metadata, not article content
- This skill focuses on:
  - discussion signals
  - community insight

- Do NOT fetch external URLs in V1 (optional future extension)

---

## Relationship with pulse-ai

This is the Hacker News module.

Future integration:

- pulse-ai-github (repos)
- pulse-ai-hn (discussion)
- pulse-ai-twitter (early signals)

Combined → full AI intelligence pipeline
