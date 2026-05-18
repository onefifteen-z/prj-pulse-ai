---
name: pulse-ai
description: >-
  This skill should be used when the user asks to "run pulse", "daily pulse",
  "fetch all signals", "pulse and publish", or invokes /pulse-ai. Orchestrates
  pulse-ai-x, pulse-ai-hn, and pulse-ai-github, builds the static site, and
  publishes to GitHub Pages.
argument-hint: "[--force] [--skip-fetch] [--no-publish]"
disable-model-invocation: true
---

# pulse-ai

Parent orchestrator for the `prj-pulse-ai` project. Runs all three signal
desks (X, Hacker News, GitHub), builds the site from `inbox/`, and publishes
by committing and pushing to `main` (GitHub Actions deploys Pages).

## When to use

- User invokes `/pulse-ai` (primary trigger)
- User says "run pulse", "daily pulse", "fetch and publish", "update the site"
- User wants all three sources in one shot instead of three separate commands

## Slash command

```
/pulse-ai
/pulse-ai --force
/pulse-ai --skip-fetch
/pulse-ai --no-publish
```

| Flag | Effect |
|------|--------|
| *(none)* | Fetch all three sources (respect per-source existence checks), build, publish |
| `--force` | Re-fetch all three even if today's/week's reports already exist |
| `--skip-fetch` | Skip fetching; only build + publish from existing `inbox/` |
| `--no-publish` | Fetch + build only; do not git commit or push |

Flags can be combined: `/pulse-ai --force --no-publish` re-fetches and builds
locally without pushing.

## Prerequisites

- Working directory: repository root (`prj-pulse-ai/`)
- Python 3 with `build/requirements.txt` installed (prefer repo `.venv` if present)
- Network access for fetches and `git push`
- `gh` / git credentials configured for push to `origin/main`

## Phase 0: Load child skills

Before fetching, read each child skill in full and follow its workflow:

| Source | Skill path | Default output |
|--------|------------|----------------|
| X | `.claude/skills/pulse-ai-x/SKILL.md` | `inbox/twitter-trending/YYYY-MM-DD.md` |
| HN | `.claude/skills/pulse-ai-hn/SKILL.md` | `inbox/hn-trending/YYYY-MM-DD.md` |
| GitHub | `.claude/skills/pulse-ai-github/SKILL.md` | `inbox/github-trending/<monday>.md` |

**Date keys**: HN and X use **today's** date (`YYYY-MM-DD`). GitHub uses **this
week's Monday** (`YYYY-MM-DD`). On Mondays all three align; other weekdays
GitHub may already have this week's file while HN/X need today's file.

## Phase 1: Fetch all sources

Skip this phase when `--skip-fetch` is set.

Run the three child workflows **in order** (X → HN → GitHub). Each child skill
owns parsing, summarization, and Markdown format — do not shortcut those steps.

### Parent overrides (only when called from `/pulse-ai`)

- **`--force`**: Treat as user confirmation to overwrite for **all** sources.
  Do not stop to ask "re-fetch?" on existing files.
- **No `--force`**: Honor each child skill's existence check. If one source
  already has a report, skip that source unless the user confirms re-fetch for
  that source only.
- **Partial failure**: If one source fails, continue with the others. Report
  failures clearly in the final summary.

### Recommended helpers

**X** — run the reference fetcher, then LLM steps from the child skill:

```bash
python .claude/skills/pulse-ai-x/reference/x_fetch.py > /tmp/pulse-x.json
```

**HN** — optional pre-filter (child skill still does summarization):

```bash
python -c "
import json, sys
sys.path.insert(0, '.claude/skills/pulse-ai-hn/reference')
from hn_fetch import fetch_top_ai
print(json.dumps(fetch_top_ai(), indent=2))
" > /tmp/pulse-hn.json
```

**GitHub** — use `web_fetch` on weekly + monthly trending URLs per child skill
(no script).

## Phase 2: Build static site

From repository root:

```bash
# Prefer project venv when it exists
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
$PY -m pip install -q -r build/requirements.txt
$PY build/build.py
```

Expected output: `built N posts → docs (prod base='/prj-pulse-ai')` with per-desk
counts. If build exits non-zero, **stop** — do not publish.

**Local preview** (only when user asks): `python build/build.py --dev` then
`python -m http.server -d docs`.

## Phase 3: Publish to GitHub Pages

Skip when `--no-publish` is set.

1. `git status` — expect changes under `inbox/` and `docs/`
2. Stage only pulse artifacts:

   ```bash
   git add inbox/twitter-trending/ inbox/hn-trending/ inbox/github-trending/ docs/
   ```

   Do **not** stage `.obsidian/`, IDE files, or unrelated edits unless the
   user explicitly asks.

3. Commit (skip if nothing to commit):

   ```bash
   git commit -m "$(cat <<'EOF'
   pulse: daily signals (X, HN, GitHub)

   EOF
   )"
   ```

   Append the date to the subject when helpful, e.g.
   `pulse: daily signals 2026-05-18`.

4. Push: `git push origin main`

5. Tell the user:
   - Commit SHA (short)
   - That **Build & deploy Pulse** workflow runs on push to `main`
   - Live site: https://onefifteen-z.github.io/prj-pulse-ai/

Do **not** force-push. If push is rejected, report the error and stop.

## Final report to user

Summarize in one message:

| Desk | Status | Output path | Notes |
|------|--------|-------------|-------|
| X | ok / skipped / failed | path or — | signal counts |
| HN | ok / skipped / failed | path or — | item count |
| GitHub | ok / skipped / failed | path or — | weekly/monthly/⭐ counts |
| Build | ok / failed | `docs/` | post count |
| Publish | pushed / skipped / nothing to commit | commit SHA | Pages URL |

## Failure handling

- **All fetches fail**: do not build or publish; explain what broke.
- **Build fails** (no markdown in inbox): fix inbox or re-run fetch; do not push.
- **Push fails**: leave local commit; user may need to pull/rebase first.
- **Unrelated dirty tree**: commit only pulse paths listed above; mention other
  unstaged files without including them.

## Example

> User: `/pulse-ai`

1. Read child skills; fetch X, HN, GitHub for today / this week
2. `python build/build.py`
3. `git add inbox/... docs/` → commit → `git push origin main`
4. Reply with desk summary + Pages URL

> User: `/pulse-ai --skip-fetch`

1. Build from existing inbox
2. Publish

## Relationship with child skills

- `pulse-ai-x`, `pulse-ai-hn`, `pulse-ai-github` — data-source modules (callable standalone via their own slash commands)
- `build/build.py` — renders `inbox/` → `docs/` + RSS
- `.github/workflows/build.yml` — deploys `docs/` to GitHub Pages on push
