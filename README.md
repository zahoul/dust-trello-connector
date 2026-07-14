# trello-to-dust-sync

A one-way sync from a Trello board into a [Dust](https://dust.tt) Data Source, built for a
**Project Health & Status Assistant** use case: a PM or eng lead can ask a Dust agent
natural-language questions about a Trello board — "What's overdue on the Mobile Redesign
board?", "Summarize what happened on the Bugs list this week", "Which cards have no owner?"
— without opening Trello.

## Architecture

```
Trello API  →  Sync script (fetch + enrich + transform)  →  Dust Data Source API
 (boards,        - one document per card                    (POST .../documents/{id})
  lists, cards,   - one "board digest" document per board
  actions)
```

The script fetches a board's lists and cards, enriches each card with computed fields
(overdue/stale flags, age, days since activity), renders it as a consistent markdown document,
and upserts it into a Dust Data Source using the card's Trello ID as the document ID. It also
generates one **board digest** document per run summarizing counts across the whole board.

### Why a Data Source sync, not an MCP server?

Dust offers two integration paths: **Data Sources** (ingest data for retrieval/RAG) and
**Remote MCP Servers** (expose live tool calls an agent can invoke, e.g. to create/move cards).
This project uses a Data Source sync because:

- The brief describes a one-way pipeline — "process project management data", "retrieve...
  via the API and connect it to Dust" — not an agentic action layer.
- The use case is read-only Q&A about board status. MCP would be the right call if the ask
  were "let an agent create/move Trello cards," but it isn't here, and building an MCP server
  would spend the time budget on tool-schema/auth plumbing instead of the retrieval/enrichment
  logic actually being evaluated.
- Dust has no native Trello connector today (Notion, Jira, Asana, Monday.com, Confluence,
  GitHub, Google Drive, HubSpot, Airtable, etc. exist; Trello doesn't), which validates a
  custom sync against Trello's REST API rather than duplicating existing Dust infrastructure.

## Setup

1. **Trello credentials**: generate an API key and token at
   https://trello.com/power-ups/admin. Find your test board's ID in its URL
   (`trello.com/b/<board_id>/...`).
2. **Dust credentials**: create a workspace, a Data Source within a space, and a workspace API
   key. Note the workspace ID and space ID from the Dust UI URLs.
   - **Gotcha:** the folder ID shown in the Dust UI URL for a data source is actually its
     *data source view* ID (`dsv_...`), which is space-scoped. The document upsert API
     (`POST .../data_sources/{dsId}/documents/{documentId}`) instead wants the underlying
     *data source* ID (`dts_...`). Get it via
     `GET /v1/w/{wId}/spaces/{spaceId}/data_source_views` and read `dataSource.sId` from the
     matching entry — using the `dsv_...` view ID here 404s even though it's the ID you see
     in the browser.
3. Copy `.env.example` to `.env` and fill in all values.
4. `pip install -r requirements.txt`

## Usage

```bash
# Full sync of all boards listed in TRELLO_BOARD_IDS
python main.py

# Sync a single board, overriding TRELLO_BOARD_IDS
python main.py --board <board_id>

# Dry run: print generated markdown documents to stdout, skip Dust entirely
python main.py --dry-run --board <board_id>
```

Each run prints a summary: boards processed, cards upserted, digest documents upserted, and
any per-card errors (a failure on one card doesn't abort the run).

## Document model

**Per card** (document ID = Trello card ID, so reruns upsert instead of duplicating):
title, list/status, description, labels, members, due date, overdue flag, card age, days since
last activity, staleness flag, and the last N comments (author + timestamp). Tags include
`board:<id>`, `list:<name>`, and conditionally `overdue` / `stale` / `unassigned` for
Dust-side filtering.

**Per board** (document ID = `digest-<board_id>-<date>`, one per day so history accumulates
across runs): cards per list, overdue count, stale count, and a list of unassigned cards.

## Validation

1. **Unit tests** (`pytest tests/`) cover the enrichment logic in isolation — overdue/stale
   flag correctness at threshold boundaries, and board digest counts — with no network access
   or credentials required.
2. **Dry-run comparison**: `python main.py --dry-run --board <id>` prints each card's generated
   markdown next to what's visible in Trello, to manually confirm the enrichment/transform
   logic (e.g. overdue flags, comment extraction) is correct before touching the Dust API.
3. **End-to-end / live demo**: after a real sync, a Dust agent is configured with this Data
   Source attached, then asked the sample questions above live against the test board, with
   answers checked against — and traceable back to — specific Trello cards.

## Assumptions, tradeoffs, and limitations

- **Full refresh, not incremental.** Every run re-fetches and re-upserts all cards. This is
  simpler and stateless, appropriate for a 3-4 hour scope. A production version would use
  Trello's `since` param on the actions endpoint (or compare `dateLastActivity`) to only
  touch changed cards, and would likely be triggered by Trello webhooks instead of manual/cron
  runs.
- **One document per card**, not one per board, so agent retrieval stays precise instead of
  dragging a whole board's text into every query.
- **Document ID = Trello card ID** is the load-bearing correctness detail: it makes the sync
  idempotent, so reruns update in place rather than accumulating duplicates.
- **Out of scope, deliberately** (not oversights): an MCP server / two-way sync (creating or
  moving Trello cards from Dust), incremental sync via webhooks, and dynamic multi-workspace/
  multi-board discovery beyond what's needed for the demo board(s).
