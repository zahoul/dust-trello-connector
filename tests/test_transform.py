from datetime import datetime, timedelta, timezone

from transform import (
    build_board_digest,
    card_created_at,
    enrich_card,
)

NOW = datetime(2026, 7, 14, tzinfo=timezone.utc)
LIST_NAMES = {"list1": "In Progress", "list2": "Done"}


def make_card(idx=1, **overrides):
    card = {
        "id": f"64a1b2c{idx:017x}",
        "name": f"Card {idx}",
        "desc": "Some description",
        "due": None,
        "dueComplete": False,
        "dateLastActivity": (NOW - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "idList": "list1",
        "idMembers": [],
        "members": [],
        "labels": [],
        "shortUrl": "https://trello.com/c/abc123",
    }
    card.update(overrides)
    return card


def test_card_created_at_decodes_known_id():
    # 0x64a1b2c3 seconds since epoch -> a real-looking date in 2023, well before "now".
    card_id = "64a1b2c30000000000000000"
    created = card_created_at(card_id)
    assert created.tzinfo is not None
    assert created < NOW
    assert created.year >= 2023


def test_overdue_true_when_past_due_and_not_complete():
    card = make_card(due=(NOW - timedelta(days=2)).isoformat().replace("+00:00", "Z"), dueComplete=False)
    enriched = enrich_card(card, LIST_NAMES, comments=[], now=NOW)
    assert enriched["is_overdue"] is True


def test_overdue_false_when_due_complete():
    card = make_card(due=(NOW - timedelta(days=2)).isoformat().replace("+00:00", "Z"), dueComplete=True)
    enriched = enrich_card(card, LIST_NAMES, comments=[], now=NOW)
    assert enriched["is_overdue"] is False


def test_overdue_false_when_no_due_date():
    card = make_card(due=None)
    enriched = enrich_card(card, LIST_NAMES, comments=[], now=NOW)
    assert enriched["is_overdue"] is False


def test_stale_true_at_threshold_boundary():
    card = make_card(dateLastActivity=(NOW - timedelta(days=7)).isoformat().replace("+00:00", "Z"))
    enriched = enrich_card(card, LIST_NAMES, comments=[], now=NOW)
    assert enriched["is_stale"] is True


def test_stale_false_just_under_threshold():
    card = make_card(dateLastActivity=(NOW - timedelta(days=6, hours=1)).isoformat().replace("+00:00", "Z"))
    enriched = enrich_card(card, LIST_NAMES, comments=[], now=NOW)
    assert enriched["is_stale"] is False


def test_unassigned_when_no_members():
    card = make_card(members=[])
    enriched = enrich_card(card, LIST_NAMES, comments=[], now=NOW)
    assert enriched["member_names"] == []


def test_board_digest_counts():
    lists = [{"id": "list1", "name": "In Progress"}, {"id": "list2", "name": "Done"}]
    board = {"id": "board1", "name": "Test Board"}

    overdue_card = make_card(idx=1, due=(NOW - timedelta(days=1)).isoformat().replace("+00:00", "Z"), dueComplete=False)
    stale_card = make_card(idx=2, dateLastActivity=(NOW - timedelta(days=10)).isoformat().replace("+00:00", "Z"))
    unassigned_card = make_card(idx=3, members=[])
    assigned_card = make_card(idx=4, members=[{"fullName": "Alice"}])

    enriched_cards = [
        enrich_card(overdue_card, LIST_NAMES, [], now=NOW),
        enrich_card(stale_card, LIST_NAMES, [], now=NOW),
        enrich_card(unassigned_card, LIST_NAMES, [], now=NOW),
        enrich_card(assigned_card, LIST_NAMES, [], now=NOW),
    ]

    digest = build_board_digest(board, lists, enriched_cards, now=NOW)

    assert "Overdue cards (1)" in digest
    assert "Stale cards (1" in digest  # only stale_card's activity is old enough to cross the threshold
    assert "Unassigned cards (3)" in digest  # overdue_card, stale_card, and unassigned_card all default to no members
