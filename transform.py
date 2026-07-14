from datetime import datetime, timezone

import config


def card_created_at(card_id):
    timestamp = int(card_id[:8], 16)
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _parse_trello_date(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def enrich_card(card, list_name_by_id, comments, now=None):
    """Combine a raw Trello card with its list name and comments into a flat dict
    of display-ready + computed fields."""
    now = now or datetime.now(timezone.utc)

    created_at = card_created_at(card["id"])
    last_activity = _parse_trello_date(card.get("dateLastActivity")) or created_at
    due = _parse_trello_date(card.get("due"))
    due_complete = bool(card.get("dueComplete"))

    age_days = (now - created_at).days
    days_since_activity = (now - last_activity).days
    is_overdue = bool(due) and not due_complete and due < now
    is_stale = days_since_activity >= config.STALE_DAYS_THRESHOLD

    members = card.get("members") or []
    member_names = [m.get("fullName") or m.get("username") for m in members]
    labels = [l.get("name") or l.get("color") for l in (card.get("labels") or [])]

    return {
        "id": card["id"],
        "name": card.get("name", ""),
        "desc": card.get("desc", ""),
        "url": card.get("shortUrl", ""),
        "list_name": list_name_by_id.get(card.get("idList"), "Unknown"),
        "labels": [l for l in labels if l],
        "member_names": [m for m in member_names if m],
        "due": due,
        "due_complete": due_complete,
        "is_overdue": is_overdue,
        "created_at": created_at,
        "age_days": age_days,
        "last_activity": last_activity,
        "days_since_activity": days_since_activity,
        "is_stale": is_stale,
        "comments": comments,
    }


def _format_comments(comments):
    if not comments:
        return "_No comments._"
    lines = []
    for action in comments:
        author = (action.get("memberCreator") or {}).get("fullName", "Unknown")
        date = action.get("date", "")
        text = (action.get("data") or {}).get("text", "")
        lines.append(f"- **{author}** ({date}): {text}")
    return "\n".join(lines)


def render_card_document(enriched):
    """Render a card's enriched data as a consistent markdown document."""
    due_line = "None"
    if enriched["due"]:
        due_line = enriched["due"].date().isoformat()
        if enriched["is_overdue"]:
            due_line += " (OVERDUE)"
        elif enriched["due_complete"]:
            due_line += " (complete)"

    return f"""# {enriched['name']}

- **Status / List:** {enriched['list_name']}
- **Labels:** {', '.join(enriched['labels']) or 'None'}
- **Members:** {', '.join(enriched['member_names']) or 'Unassigned'}
- **Due date:** {due_line}
- **Card age:** {enriched['age_days']} days
- **Days since last activity:** {enriched['days_since_activity']} ({'stale' if enriched['is_stale'] else 'active'})
- **URL:** {enriched['url']}

## Description

{enriched['desc'] or '_No description._'}

## Recent comments

{_format_comments(enriched['comments'])}
"""


def card_tags(enriched, board_id):
    tags = [
        "trello",
        f"board:{board_id}",
        f"list:{enriched['list_name']}",
    ]
    if enriched["is_overdue"]:
        tags.append("overdue")
    if enriched["is_stale"]:
        tags.append("stale")
    if not enriched["member_names"]:
        tags.append("unassigned")
    return tags


def digest_document_id(board_id, now=None):
    now = now or datetime.now(timezone.utc)
    return f"digest-{board_id}-{now:%Y-%m-%d}"


def build_board_digest(board, lists, enriched_cards, now=None):
    now = now or datetime.now(timezone.utc)

    cards_per_list = {lst["name"]: 0 for lst in lists}
    for card in enriched_cards:
        cards_per_list[card["list_name"]] = cards_per_list.get(card["list_name"], 0) + 1

    overdue = [c for c in enriched_cards if c["is_overdue"]]
    stale = [c for c in enriched_cards if c["is_stale"]]
    unassigned = [c for c in enriched_cards if not c["member_names"]]

    per_list_lines = "\n".join(f"- {name}: {count}" for name, count in cards_per_list.items())
    overdue_lines = "\n".join(f"- {c['name']} (due {c['due'].date().isoformat()})" for c in overdue) or "_None_"
    stale_lines = "\n".join(
        f"- {c['name']} ({c['days_since_activity']} days since activity)" for c in stale
    ) or "_None_"
    unassigned_lines = "\n".join(f"- {c['name']}" for c in unassigned) or "_None_"

    return f"""# Board Digest: {board.get('name', board.get('id'))}

Generated: {now.isoformat()}

## Cards per list

{per_list_lines}

## Overdue cards ({len(overdue)})

{overdue_lines}

## Stale cards ({len(stale)}, no activity in >= {config.STALE_DAYS_THRESHOLD} days)

{stale_lines}

## Unassigned cards ({len(unassigned)})

{unassigned_lines}
"""
