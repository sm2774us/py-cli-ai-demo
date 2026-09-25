# pycli-wordstat — Python 3.13 AI-refactor teaching example

A deliberately **sub-optimal** CLI (`wordstat`) plus a fully automated,
human-gated pipeline for having an AI agent improve it, benchmark the
improvement, and ship it through PR review, changelog, and semver
release — using **only free-tier tooling**.

## What's sub-optimal here (on purpose)

`src/pycli/wordstat.py`:
- `count_words` uses a list with linear search per word → **O(n²)**.
- `top_n_words` does a linear max-scan per output slot → **O(n·k)**.
- `tokenize` builds strings via repeated concatenation.

This is the "before" state an AI agent is asked to optimize (target:
`dict`/`Counter` + `heapq.nlargest`, i.e. O(n log k)).

## Stack

| Concern | Tool |
|---|---|
| Runtime | Python 3.13 |
| Env/deps/build | [`uv`](https://docs.astral.sh/uv/) |
| Tests | `pytest` + `pytest-cov`, **100% coverage gate** (`--cov-fail-under=100`) |
| Style | Google Python Style Guide, enforced via `ruff` (`pydocstyle=google`) |
| CI | GitHub Actions |
| AI agent (free tier) | **Google Gemini `gemini-3.5-flash-lite`**, called directly via the REST `generateContent` endpoint |

### Why Gemini only, and why raw REST instead of an SDK/Action

Claude's and OpenAI's APIs are both pay-as-you-go with no ongoing free
tier, so neither fits a "free tier for learning" repo. Gemini's
`gemini-3.5-flash-lite` is available free via Google AI Studio, so it's
the only agent wired into automation here. Rather than depend on a
third-party GitHub Action, `scripts/ai_improve.py` calls the endpoint
directly:

```bash
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent" \
  -H "Content-Type: application/json" \
  -H "X-goog-api-key: $GEMINI_API_KEY" \
  -X POST -d '{"contents": [{"parts": [{"text": "..."}]}]}'
```

`scripts/ai_improve.py` is that same call in Python (`urllib`, no
dependencies), with a prompt asking for the full new content of the
source file and its test file, which it then parses and writes to disk.

> **GitHub Copilot** still works as a manually-triggered *third* free
> comparison point (its coding agent isn't a scriptable Action step) —
> see `docs/copilot-agent-note.md`.

## Benchmark corpus note

`scripts/benchmark.py` generates its corpus with distinct alphabetic
words (`a`, `b`, ..., `z`, `aa`, `ab`, ...) rather than `word0`,
`word1`, etc. — `tokenize()` strips digits, so a numeric-suffix
vocabulary silently collapses into a single token and defeats
`--vocab` entirely. With a genuine `--words 20000 --vocab 15000`
corpus the sub-optimal implementation runs 100-300x slower than a
correct `Counter`/`heapq.nlargest` fix, which is a large enough margin
that CI timing noise can't cause a false failure.

## Local setup

```bash
uv sync --group dev
uv run pytest              # 100%-coverage-gated test run
uv run ruff check src tests scripts
uv run python scripts/benchmark.py --words 20000 --vocab 15000
uv run wordstat some_file.txt -n 10

# try the AI rewrite locally (needs a free Gemini API key from
# https://aistudio.google.com/apikey)
export GEMINI_API_KEY=your_key_here
uv run python scripts/ai_improve.py \
  --instruction "improve algorithm and performance" \
  --file src/pycli/wordstat.py \
  --tests tests/test_wordstat.py
```

## The automated workflows

### 1) `ai-improve.yml` — "improve algorithm and performance"

Manual-trigger only (`workflow_dispatch`) — this **is** the supervision
gate. Runs baseline benchmark + tests, calls Gemini directly via REST to
rewrite `wordstat.py` + its tests, re-lints, re-tests (100% coverage
still enforced), re-benchmarks, **fails the job outright if the change
isn't measurably faster**, then opens a PR and stops. Nothing merges
without a human clicking "Approve and merge."

Trigger it:

```bash
# from Win11 cmd/PowerShell or Ubuntu terminal, via GitHub CLI
gh workflow run ai-improve.yml -f instruction="improve algorithm and performance"
```

Or use the "Run workflow" button on the Actions tab.

**Required repo secret:** `GEMINI_API_KEY` (free tier from Google AI
Studio — https://aistudio.google.com/apikey).

> If you were testing with a real key in a terminal, treat any key
> that's ever been pasted somewhere shareable (chat, ticket, log) as
> compromised and rotate it at https://aistudio.google.com/apikey
> before using it as a repo secret.

### 2) `open-pr.yml` — for your own hand-written changes

For changes you write yourself, no AI involved: create a feature
branch, commit and push it as usual — `ci.yml` now runs lint/tests on
every branch push, not just on `main`/`master`, so you get feedback
immediately. When you're done, run this to open the PR for you:

```bash
gh workflow run open-pr.yml -f branch=feature/my-change -f title="My change"
```

It re-verifies lint + tests on that exact branch before opening
anything, and fails with a clear message if there's nothing to PR
(branch has no commits ahead of the default branch) rather than
opening an empty one. It never approves or merges — same manual
review requirement, enforced the same way by branch protection, as
every other PR in this repo.

### 3) `changelog-release.yml` — "changelog"

Manual-trigger only. Takes a PR number and generates a `CHANGELOG.md`
section from the commit log, bumps semver (`patch`/`minor`/`major`),
tags, and cuts a GitHub Release. No AI involved — releases are
deterministic on purpose. Works identically whether the merged PR came
from `ai-improve.yml` or `open-pr.yml`. Handles two flows:

- **You already reviewed, approved, and merged the PR yourself** (the
  normal path) — run this afterward with the same PR number; it
  detects the PR is already merged and skips straight to generating
  the changelog/tag/release from what's on `main`.
- **The PR is approved but still open** — this step merges it first.
  No `--admin` override either way: branch protection still blocks an
  unapproved merge.

```bash
gh workflow run changelog-release.yml -f pr_number=42 -f bump=patch
```

## Human review is enforced, not just convention

`ai-improve.yml` never merges anything — it stops at opening a PR. But
workflow behavior alone isn't a guarantee: a future edit could add an
auto-merge line by mistake. Branch protection closes that gap at the
GitHub level instead of the workflow level, requiring: at least one
human approval, the `ci.yml` checks passing, and — with
`enforce_admins: true` — this applies even to the repo owner, so
there's no bypass.

**Recommended: do this once by hand** — repo → **Settings** →
**Branches** → **Add branch protection rule** → branch name pattern
matching your default branch → check **"Require a pull request before
merging"** (approvals: 1) and **"Require status checks to pass"** (add
`test`) → check **"Do not allow bypassing the above settings"** →
**Save**. Takes under a minute, needs no extra credentials.

**Or, to automate it**: `setup-branch-protection.yml` does the same
thing via the API — but that API is admin-only, and the workflow's
built-in `GITHUB_TOKEN` can never call it (this is a hard GitHub
platform limitation, not something any workflow permission can grant).
Automating it requires a real fine-grained Personal Access Token with
**Administration: Read and write**, stored as the repo secret
`ADMIN_PAT` (the workflow file's header comment has the exact steps).
Only worth it if you plan to reuse this repo as a template often;
otherwise the one-time manual click above is simpler and avoids
holding an admin-scoped token at all.

`PR`s the bot opens are authored as `github-actions[bot]`, not as you,
so you can review and approve your own repo's AI-generated PRs
normally either way:

```bash
gh pr review <number> --approve
gh pr merge <number> --squash
```

If you (or `changelog-release.yml`) try to merge before approving,
GitHub rejects it outright — that rejection is the protection working
as intended, not a bug.

## Economical AI usage (avoiding token-maxxing)

- The improve-workflow prompt is short, scoped to exactly two files,
  names the exact target implementation (`collections.Counter`,
  `heapq.nlargest`, `re.findall`) instead of leaving the approach
  open-ended, and `gemini-3.5-flash-lite` is the smallest/cheapest
  tier that can do this reliably.
- The self-heal retry loop (lint → test → benchmark, up to 4 attempts)
  only calls Gemini again when something actually failed, feeding it
  the specific error instead of re-explaining the whole task.
- The workflow **fails fast** (lint → test → benchmark → gate) so a bad
  or wasteful AI run never reaches PR review, and branch protection
  means a bad PR can't reach `main` even if review is skipped.
- Free-tier key only — this repo is for building intuition before
  spending money on a paid plan/product.

## Layout

```
src/pycli/wordstat.py         sub-optimal CLI (the "before")
tests/test_wordstat.py        100%-coverage pytest suite
tests/test_ai_improve.py      tests for the Gemini self-heal loop
tests/test_wrap_comments.py   tests for the comment auto-fixer
scripts/benchmark.py          before/after timing harness (tokenize-safe corpus)
scripts/ai_improve.py         Gemini REST caller + self-heal retry loop
scripts/wrap_comments.py      auto-fixer for over-long comment lines
.github/workflows/ci.yml                     lint + 100%-coverage gate on every push/PR
.github/workflows/ai-improve.yml             manual: Gemini rewrite -> self-heal -> PR
.github/workflows/changelog-release.yml      manual: merge PR -> changelog -> semver tag
.github/workflows/setup-branch-protection.yml  manual, one-time: enforce human review on main
```
