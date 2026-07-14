"""Thin wrapper around the Trello REST API."""

import requests

import config

BASE_URL = "https://api.trello.com/1"

CARD_FIELDS = "name,desc,due,dueComplete,dateLastActivity,idList,idMembers,labels,pos,shortUrl"
MEMBER_FIELDS = "fullName,username"


def _auth_params():
    return {"key": config.TRELLO_API_KEY, "token": config.TRELLO_TOKEN}


def _get(path, params=None):
    query = _auth_params()
    if params:
        query.update(params)
    resp = requests.get(f"{BASE_URL}{path}", params=query, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path, params=None):
    query = _auth_params()
    if params:
        query.update(params)
    resp = requests.post(f"{BASE_URL}{path}", params=query, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _put(path, params=None):
    query = _auth_params()
    if params:
        query.update(params)
    resp = requests.put(f"{BASE_URL}{path}", params=query, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_board(board_id):
    return _get(f"/boards/{board_id}", {"fields": "id,name,url"})


def get_lists(board_id):
    return _get(f"/boards/{board_id}/lists", {"fields": "name"})


def get_cards(board_id):
    return _get(
        f"/boards/{board_id}/cards",
        {
            "fields": CARD_FIELDS,
            "members": "true",
            "member_fields": MEMBER_FIELDS,
        },
    )


def get_card_comments(card_id, limit=5):
    return _get(
        f"/cards/{card_id}/actions",
        {"filter": "commentCard", "limit": limit},
    )


def get_me():
    return _get("/members/me", {"fields": "fullName,username"})


def get_board_labels(board_id):
    return _get(f"/boards/{board_id}/labels", {"fields": "name,color"})


def create_label(board_id, name, color):
    return _post("/labels", {"name": name, "color": color, "idBoard": board_id})


def create_list(board_id, name):
    return _post("/lists", {"name": name, "idBoard": board_id})


def create_card(list_id, name, desc="", due=None, id_members=None, id_labels=None):
    params = {"idList": list_id, "name": name, "desc": desc}
    if due:
        params["due"] = due
    if id_members:
        params["idMembers"] = ",".join(id_members)
    if id_labels:
        params["idLabels"] = ",".join(id_labels)
    return _post("/cards", params)


def add_comment(card_id, text):
    return _post(f"/cards/{card_id}/actions/comments", {"text": text})


def set_card_due_complete(card_id, complete=True):
    return _put(f"/cards/{card_id}", {"dueComplete": "true" if complete else "false"})


def archive_list(list_id):
    return _put(f"/lists/{list_id}/closed", {"value": "true"})


def archive_card(card_id):
    return _put(f"/cards/{card_id}", {"closed": "true"})
