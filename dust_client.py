"""Thin wrapper around the Dust Data Source documents API."""

import requests

import config


def upsert_document(document_id, text, tags=None):
    url = (
        f"{config.DUST_API_URL}/v1/w/{config.DUST_WORKSPACE_ID}"
        f"/spaces/{config.DUST_SPACE_ID}/data_sources/{config.DUST_DATASOURCE_ID}"
        f"/documents/{document_id}"
    )
    headers = {
        "Authorization": f"Bearer {config.DUST_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {"text": text, "tags": tags or []}

    resp = requests.post(url, json=body, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()
