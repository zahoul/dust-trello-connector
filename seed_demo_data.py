"""Populates a Trello test board with realistic demo data (lists, labels, cards
with varied due dates/assignees, and comments) so the sync script has something
meaningful to process.

Usage:
    python seed_demo_data.py               # seeds the first board in TRELLO_BOARD_IDS
    python seed_demo_data.py --board <id>  # seeds a specific board

Idempotent: lists and labels are reused by name instead of duplicated, and a card
is skipped if a card with the same name already exists on the board. This makes
it safe to re-run after adding new entries to CARDS below (e.g. to top up demo
data before a live walkthrough) without duplicating everything already seeded.
"""

import argparse
from datetime import datetime, timedelta, timezone

import config
import trello_client

NOW = datetime.now(timezone.utc)

LIST_NAMES = ["Backlog", "In Progress", "Review", "Done"]

LABEL_DEFS = {
    "Bug": "red",
    "Feature": "green",
    "Chore": "yellow",
    "Blocked": "purple",
}

# (list, name, desc, due_offset_days, done, labels, assigned, comments)
CARDS = [
    ("Backlog", "Set up CI pipeline", "Add GitHub Actions for lint + test on every PR.",
     None, False, ["Chore"], False, []),
    ("Backlog", "Research analytics vendor", "Compare Amplitude vs. Mixpanel for product analytics.",
     14, False, ["Feature"], False, []),
    ("In Progress", "Fix login crash on Android", "Users on Android 12 report a crash on login with SSO enabled.",
     -3, False, ["Bug"], True,
     ["Repro'd on Pixel 6, Android 13 — stack trace points to the SSO callback handler.",
      "Looks like a null token race condition. Working on a fix now."]),
    ("In Progress", "Implement dark mode", "Add a dark theme toggle across the web app.",
     5, False, ["Feature"], True, []),
    ("In Progress", "Refactor auth middleware", "Clean up the legacy session-check middleware before the compliance audit.",
     10, False, ["Chore"], False, []),
    ("Review", "PR: Add payment retry logic", "Retries failed payment webhooks up to 3x with backoff.",
     1, False, ["Bug"], True,
     ["Looks good, one comment on the backoff constants.", "Updated, ready for another pass."]),
    ("Review", "PR: Update onboarding copy", "New copy for the welcome email + first-run tooltip.",
     -1, False, ["Feature"], False, []),
    ("Done", "Migrate DB to Postgres 15", "Completed the version upgrade with zero downtime.",
     -10, True, ["Chore"], True, []),
    ("Done", "Add dark mode toggle in settings", "Shipped behind a feature flag, now fully rolled out.",
     -6, True, ["Feature"], False, []),
    ("Done", "Fix flaky test suite", "Root cause was shared test DB state between parallel runners.",
     -4, True, ["Bug"], True,
     ["Fixed by isolating test DB schemas per worker.", "Confirmed green for 20 consecutive runs."]),
    # --- extra batch: more volume/variety for the live demo ---
    ("Backlog", "Add SSO support for Okta", "Enterprise customers are asking for SAML/Okta login.",
     21, False, ["Feature"], False, []),
    ("Backlog", "Investigate flaky checkout on Safari", "Checkout intermittently hangs on Safari 17, no repro yet.",
     None, False, ["Bug"], False, []),
    ("Backlog", "Write incident postmortem template", "Standardize the postmortem doc format for on-call.",
     None, False, ["Chore"], False, []),
    ("In Progress", "Rate-limit public API endpoints", "Add per-key rate limiting to prevent abuse of /v1/export.",
     3, False, ["Feature"], True, []),
    ("In Progress", "Fix broken CSV export for large accounts", "Export times out for accounts with 100k+ rows.",
     -1, False, ["Bug", "Blocked"], True,
     ["Blocked on the data team provisioning a read replica for the export job.",
      "Replica ETA pushed to next week.",
      "Confirmed timeout is in the query, not the file generation step.",
      "Tried batching in 10k chunks, still too slow.",
      "Data team says replica is provisioned, retesting now.",
      "Still blocked — replica has stale data, escalating."]),
    ("Review", "PR: Rework pagination for /invoices API", "Cursor-based pagination to replace offset pagination.",
     2, False, ["Chore"], False, []),
    ("Review", "PR: Add retry telemetry dashboard", "Grafana dashboard tracking webhook retry counts and latency.",
     -2, False, ["Feature"], True,
     ["One nit on the panel naming, otherwise LGTM."]),
    ("Done", "Upgrade Node to v22 across services", "Rolled out across all backend services without incident.",
     -15, True, ["Chore"], False, []),
    ("Done", "Add SOC2 audit logging", "Structured audit logs for all admin actions, shipped for the compliance review.",
     -8, True, ["Feature"], True, []),
    ("Done", "Resolve race condition in webhook dispatcher", "Two workers could double-send the same webhook under load.",
     -5, True, ["Bug"], True,
     ["Root cause was a missing DB-level lock on claim.", "Verified fix under load test, no more duplicates."]),
]


def iso(days_offset):
    return (NOW + timedelta(days=days_offset)).isoformat()


def get_or_create_lists(board_id):
    existing = {lst["name"]: lst["id"] for lst in trello_client.get_lists(board_id)}
    result = {}
    for name in LIST_NAMES:
        if name in existing:
            result[name] = existing[name]
        else:
            result[name] = trello_client.create_list(board_id, name)["id"]
            print(f"Created list: {name}")
    return result


def get_or_create_labels(board_id):
    existing = {l["name"]: l["id"] for l in trello_client.get_board_labels(board_id) if l.get("name")}
    result = {}
    for name, color in LABEL_DEFS.items():
        if name in existing:
            result[name] = existing[name]
        else:
            result[name] = trello_client.create_label(board_id, name, color)["id"]
            print(f"Created label: {name}")
    return result


def seed(board_id):
    me = trello_client.get_me()
    my_id = me["id"]

    # Trello's write endpoints (POST /lists, /labels, /cards) require the full 24-char
    # board ID, not the short link from the URL — resolve it via a GET first.
    board = trello_client.get_board(board_id)
    board_id = board["id"]

    print(f"Seeding board {board_id} as {me.get('fullName', my_id)}")

    lists = get_or_create_lists(board_id)
    labels = get_or_create_labels(board_id)

    existing_card_names = {c["name"] for c in trello_client.get_cards(board_id)}

    created = 0
    skipped = 0
    for list_name, name, desc, due_offset, done, label_names, assign_me, comments in CARDS:
        if name in existing_card_names:
            skipped += 1
            continue

        due = iso(due_offset) if due_offset is not None else None
        id_labels = [labels[l] for l in label_names]
        id_members = [my_id] if assign_me else None

        card = trello_client.create_card(
            lists[list_name], name, desc=desc, due=due, id_members=id_members, id_labels=id_labels
        )

        if done:
            # dueComplete isn't settable at creation time; flip it right after.
            trello_client.set_card_due_complete(card["id"], complete=True)

        for text in comments:
            trello_client.add_comment(card["id"], text)

        created += 1
        print(f"  [{list_name}] {name}")

    print(f"\nDone. {len(lists)} lists, {len(labels)} labels. Created {created} new cards, skipped {skipped} already present.")
    print("Note: Trello sets dateLastActivity to the real creation time, so freshly seeded "
          "cards won't show up as 'stale' until enough real days pass — that's expected, and "
          "today's batch will naturally cross a 7-day staleness threshold by next week.")


def main():
    parser = argparse.ArgumentParser(description="Seed a Trello board with demo data.")
    parser.add_argument("--board", help="Board ID to seed (defaults to the first configured board).")
    args = parser.parse_args()

    board_id = args.board or (config.TRELLO_BOARD_IDS[0] if config.TRELLO_BOARD_IDS else None)
    if not board_id:
        raise SystemExit("No board ID given. Pass --board <id> or set TRELLO_BOARD_IDS in .env.")

    seed(board_id)


if __name__ == "__main__":
    main()
