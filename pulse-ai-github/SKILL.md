---
name: pulse-ai-github
description: This skill should be used when the user asks for "GitHub trending",
  "trending repos", "open-source weekly ranking", "GitHub monthly", "what's hot
  on GitHub", "AI open-source ranking", or invokes /pulse-ai-github. Fetches
  GitHub Trending weekly and monthly lists into a Markdown report.
argument-hint: "[output-dir]"
---

# pulse-ai-github

GitHub Trending data-source skill for the `pulse-ai` project. Fetches the
weekly and monthly GitHub Trending pages in parallel, marks the intersection,
and writes a Markdown report named after the current week's Monday.

## When to use this skill

- User invokes the slash command `/pulse-ai-github` (primary trigger)
- User says "show me GitHub weekly", "GitHub trending", "GitHub monthly",
  "what's hot on GitHub recently"
- Called by the parent `pulse-ai` skill as a sub-module

**This skill does not fetch the daily list.** The 24-hour window is too noisy
(a single retweet, marketing burst, or coordinated star push can land a repo
on the daily list), and the signal-to-noise ratio is poor for AI intelligence
purposes. If the user explicitly asks for "daily", briefly explain why this
skill skips the daily list (high noise, low cost to manipulate, signal heavily
overlaps weekly), and offer to fetch the weekly list instead.

## Slash command invocation

In Claude Code, the user types:

```
/pulse-ai-github
```

Without arguments, the default output directory is `inbox/github-trending/`
(relative to the current working directory).

With an argument, override the output directory:

```
/pulse-ai-github reports/trending
```

## Data source notes (important context)

GitHub **does not provide an official trending API**. This skill scrapes the
HTML pages directly.

URLs to fetch (always both, in parallel):

- **Weekly**: `https://github.com/trending?since=weekly`
- **Monthly**: `https://github.com/trending?since=monthly`

Each page may return anywhere between roughly 10 and 25 repos. GitHub does not
publish the exact count rule. **Do not assume a fixed number** — process
whatever comes back.

## Workflow (full)

When triggered, follow these steps strictly:

### Step 1: Compute this week's Monday date

Not today's date — the date of Monday in the current week.

- If today is Monday, use today
- If today is Tuesday through Sunday, walk back to this week's Monday

Filename format: `YYYY-MM-DD.md` (example: `2026-04-27.md`)

### Step 2: Check if this week's Markdown already exists

Default output directory is `inbox/github-trending/` relative to the current working
directory, overridable by the slash command argument.

Full path: `<output-dir>/<this-monday-date>.md`, e.g.
`inbox/github-trending/2026-04-27.md`.

**If the file already exists, tell the user "This week's report already exists:
<path>" and ask whether to force a re-fetch.** Wait for explicit confirmation
("re-fetch", "overwrite") before proceeding. Otherwise stop.

The purpose: multiple triggers within the same week do not cause redundant
fetches, saving tokens and reducing pressure on GitHub.

### Step 3: Fetch weekly and monthly in parallel

Call web_fetch for both URLs concurrently:

1. `web_fetch("https://github.com/trending?since=weekly")`
2. `web_fetch("https://github.com/trending?since=monthly")`

**Fetch method**: use web_fetch to retrieve the HTML, then extract repo
information directly from the returned content. Do not write Python or Node
scripts to scrape — the data volume is small, the page structure changes
unpredictably, and LLM-based extraction is more robust than CSS selectors.
When GitHub redesigns the page, a selector-based scraper breaks; an LLM can
still read the content.

### Step 4: Extract fields per repo

For each repo, extract:

```json
{
  "rank": 1,
  "full_name": "owner/repo",
  "url": "https://github.com/owner/repo",
  "description": "one-line repo description",
  "language": "Python",
  "total_stars": 12345,
  "period_stars": 678,
  "period": "weekly"
}
```

Field notes:

- `period_stars`: stars gained in the current period, shown on the trending
  page as "X stars this week" / "X stars this month"
- `description` may be empty — GitHub allows repos without a description
- `language` may be null — some repos have no detectable primary language
- `period` is `"weekly"` or `"monthly"` to mark the source list

### Step 5: Mark intersection within the original lists (no grouping, no dedup)

Do not create a separate "dual-list" section. Keep the weekly and monthly
lists complete in their own sections, and add a ⭐ marker to repos that appear
in both lists.

Specific rules:

- Use `full_name` (e.g. `owner/repo`) as the matching key to identify which
  repos appear in both lists
- When rendering the weekly section, prefix the title with ⭐ if the repo also
  appears in the monthly list
- When rendering the monthly section, prefix the title with ⭐ if the repo
  also appears in the weekly list
- Repos that appear in only one list get no marker

This means the same repo will appear twice in the final Markdown (once in
weekly, once in monthly), each with its own ⭐ marker. This is intentional —
in the weekly context ⭐ means "not just hot this week, also up across the
month"; in the monthly context ⭐ means "still accelerating this week".
Each appearance carries different meaning.

**Important**: do not apply AI keyword filters, programming language filters,
or anti-spam heuristics. Keep everything, let the user judge.

### Step 6: Generate the Markdown report

Render using the format below and write to
`<output-dir>/<this-monday-date>.md`.

### Step 7: Report back to the user

Brief feedback:

- How many repos were fetched (weekly N / monthly M / Z marked with ⭐)
- Where the report was saved
- If any source failed, state it clearly

## Markdown output format

```markdown
# GitHub Trending - Week of 2026-04-27

> Fetched at: 2026-04-29 14:30
> Weekly: N repos · Monthly: M repos · Z repos appear in both (marked ⭐)

## Weekly

### ⭐ 1. owner/repo

- **Language**: Python
- **Total stars**: 12.3k
- **This week**: +678
- **Description**: one-line description
- **URL**: https://github.com/owner/repo

### 2. another/repo

- **Language**: Rust
- **Total stars**: 5.2k
- **This week**: +890
- **Description**: ...
- **URL**: https://github.com/another/repo

### ⭐ 3. ...

## Monthly

### ⭐ 1. owner/repo

- **Language**: Python
- **Total stars**: 12.3k
- **This month**: +2,345
- **Description**: one-line description
- **URL**: https://github.com/owner/repo

### 2. yet-another/repo

- **Language**: TypeScript
- **Total stars**: 23.1k
- **This month**: +3,456
- **Description**: ...
- **URL**: https://github.com/yet-another/repo

### ⭐ 3. ...
```

Within each section, sort by `period_stars` descending (weekly section by
this-week stars, monthly section by this-month stars). The numbering
(1, 2, 3...) is the rank within the section, not GitHub's original rank,
though they usually match.

⭐ marker rule: if a repo appears in both lists, prefix the title with ⭐ in
both sections. Repos that appear in only one section get no marker.

## Output directory convention

```
<working-dir>/
└── inbox/github-trending/
    ├── 2026-04-13.md       # week of April 13
    ├── 2026-04-20.md       # week of April 20
    ├── 2026-04-27.md       # this week
    └── ...
```

Filename = the Monday date of that week (ISO 8601 `YYYY-MM-DD`). The existence
check in Step 2 is based on this naming rule.

## Failure handling

**Important: do not return empty data and pretend it succeeded.** That would
make the user think there were no trending repos this week.

- **web_fetch network error**: retry once. If it still fails, tell the user
  clearly: "GitHub fetch failed, reason: xxx". Do not generate an empty
  Markdown file.
- **HTML structure change causing 0 parsed repos**: stop immediately and tell
  the user "GitHub may have redesigned the page structure, this skill needs
  updating". Do not proceed.
- **One side fails** (weekly ok, monthly fails, or vice versa): tell the user
  which side failed and ask whether to generate the report with the
  single-side data. If the user agrees, prefix the Markdown with
  "⚠️ Monthly fetch failed, this report contains weekly data only" (or vice
  versa).
- **Parsed count is anomalously low** (e.g. only 1-2 repos when usually 10+):
  treat as a parse failure; the page may have loaded partially.

## Rate limiting

The GitHub trending pages are public, no auth needed, but avoid hammering:

- Skip refetching when this week's Markdown already exists (Step 2's existence
  check handles this)
- When the user triggers consecutive "re-fetch" actions, wait at least 1
  minute between them
- On 429 or 503, wait 5 minutes before retrying

## Relationship with the parent pulse-ai project

This skill is the GitHub data source module of the `pulse-ai` project.

**Standalone use** (primary scenario):

- User triggers via `/pulse-ai-github`
- Output is Markdown to `inbox/github-trending/<this-monday>.md` for the user to read

**Called by the parent `pulse-ai` skill** (future):

- Parent skill specifies a different output dir (e.g. `pulse-ai/inbox/`)
- Parent skill decides whether JSON output is needed (extend later if so)

Sibling skills (planned):

- `pulse-ai-hn`: Hacker News
- `pulse-ai-arxiv`: arxiv AI categories
- `pulse-ai-twitter`: Twitter (via Browser MCP)
- `pulse-ai-rss`: generic RSS

## Example interactions

### Example 1: standard trigger, first time this week

> User: `/pulse-ai-github`

Steps:

1. Compute this week's Monday (assume 2026-04-27)
2. Check that `inbox/github-trending/2026-04-27.md` does not exist
3. Fetch weekly and monthly in parallel
4. Extract fields, mark intersection
5. Generate `inbox/github-trending/2026-04-27.md`
6. Tell the user: "Generated this week's GitHub Trending report:
   inbox/github-trending/2026-04-27.md (weekly 18 / monthly 22 / 5 also appear in
   both, marked ⭐)"

### Example 2: this week already fetched

> User: `/pulse-ai-github`

Steps:

1. Detect that `inbox/github-trending/2026-04-27.md` already exists
2. Reply: "This week's report already exists:
   inbox/github-trending/2026-04-27.md. Re-fetch?"
3. Wait for confirmation

> User: re-fetch

Steps:

1. Continue with the fetch flow, overwriting the existing file
2. Notify the user when done

### Example 3: custom output directory

> User: `/pulse-ai-github reports/weekly`

Steps:

1. Use `reports/weekly/` as the output directory
2. File path becomes `reports/weekly/2026-04-27.md`
3. The rest of the flow is unchanged

### Example 4: user asks for daily list

> User: show me today's GitHub daily

Steps:

1. Do not fetch `?since=daily`
2. Briefly explain: "This skill does not fetch the daily list. The 24-hour
   window is too noisy — a single retweet or marketing push can land a repo
   on the daily list, so the signal-to-noise ratio is worse than the weekly
   list. May I fetch the weekly list instead? (this week's report will be
   saved to inbox/github-trending/<this-monday>.md)"
3. Wait for the user to confirm before running the standard flow

### Example 5: monthly fetch fails

The monthly URL returns 503 during fetch.

Steps:

1. Retry once, still fails
2. Tell the user: "Monthly fetch failed (GitHub 503). The weekly fetch
   succeeded with 18 repos. Generate the report with weekly data only?"
3. If the user agrees: generate the Markdown with a "⚠️ Monthly fetch failed"
   notice at the top, render only the Weekly section. Since monthly data is
   missing, no ⭐ markers can be applied — render all weekly entries without
   the marker.
4. If the user declines: do not generate a file, suggest retrying later.
