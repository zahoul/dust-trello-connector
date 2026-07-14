"""Orchestrates: Trello fetch -> transform/enrich -> Dust Data Source upsert.

Usage:
    python main.py                     # full sync of all configured boards
    python main.py --dry-run           # print generated documents, no Dust calls
"""

import argparse
import sys
from datetime import datetime, timezone

import config
import dust_client
import trello_client

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from transform import (
    build_board_digest,
    card_tags,
    digest_document_id,
    enrich_card,
    render_card_document,
)


def sync_board(board_id, now, dry_run):
    errors = []
    cards_upserted = 0
    digests_upserted = 0

    board = trello_client.get_board(board_id)
    lists = trello_client.get_lists(board_id)
    list_name_by_id = {lst["id"]: lst["name"] for lst in lists}
    cards = trello_client.get_cards(board_id)

    enriched_cards = []
    for card in cards:
        try:
            comments = trello_client.get_card_comments(card["id"], limit=config.COMMENTS_PER_CARD)
            enriched = enrich_card(card, list_name_by_id, comments, now=now)
            enriched_cards.append(enriched)

            document = render_card_document(enriched)
            tags = card_tags(enriched, board_id)

            if dry_run:
                print(f"--- card {card['id']} ({enriched['name']}) ---")
                print(document)
            else:
                dust_client.upsert_document(card["id"], document, tags=tags)
            cards_upserted += 1
        except Exception as exc:  # noqa: BLE001 - one bad card shouldn't abort the run
            errors.append((card.get("id", "?"), str(exc)))

    try:
        digest_text = build_board_digest(board, lists, enriched_cards, now=now)
        doc_id = digest_document_id(board_id, now=now)
        if dry_run:
            print(f"--- digest {doc_id} ---")
            print(digest_text)
        else:
            dust_client.upsert_document(doc_id, digest_text, tags=["trello", f"board:{board_id}", "digest"])
        digests_upserted += 1
    except Exception as exc:  # noqa: BLE001
        errors.append((f"digest:{board_id}", str(exc)))

    return cards_upserted, digests_upserted, errors


def main():
    parser = argparse.ArgumentParser(description="Sync Trello board data into a Dust Data Source.")
    parser.add_argument("--dry-run", action="store_true", help="Print generated documents instead of calling the Dust API.")
    args = parser.parse_args()

    config.validate(require_dust=not args.dry_run)

    board_ids = config.TRELLO_BOARD_IDS
    now = datetime.now(timezone.utc)

    total_cards = 0
    total_digests = 0
    all_errors = []

    for board_id in board_ids:
        cards_upserted, digests_upserted, errors = sync_board(board_id, now, args.dry_run)
        total_cards += cards_upserted
        total_digests += digests_upserted
        all_errors.extend(errors)

    print("\n=== Sync summary ===")
    print(f"Boards processed: {len(board_ids)}")
    print(f"Cards upserted: {total_cards}")
    print(f"Digest documents upserted: {total_digests}")
    print(f"Errors: {len(all_errors)}")
    for item_id, message in all_errors:
        print(f"  - {item_id}: {message}")

    sys.exit(1 if all_errors else 0)


if __name__ == "__main__":
    main()
