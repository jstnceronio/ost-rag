from __future__ import annotations
from datetime import datetime
from typing import Any

from app.confluence.models import ConfluencePage


# Don't like the format of the Confluence Date
def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def map_page(payload: dict[str, Any], base_url: str, body_format: str = "storage") -> ConfluencePage:
    body = payload.get("body", {}).get(body_format, {})
    version = payload.get("version", {})
    history = payload.get("history", {})
    links = payload.get("_links", {})
    ancestors = payload.get("ancestors", [])
    parent_id = str(ancestors[-1]["id"]) if ancestors else None
    url = links.get("webui")

    if url and not url.startswith("http"):
        url = f"{base_url}{url}"

    return ConfluencePage(
        id=str(payload["id"]),
        title=payload["title"],
        space_id=str(payload["space"]["id"]) if payload.get("space", {}).get("id") is not None else None,
        parent_id=parent_id,
        status=payload.get("status"),
        url=url,
        body_storage=body.get("value", ""),
        version=version.get("number"),
        created_at=_parse_datetime(history.get("createdDate")),
        updated_at=_parse_datetime(version.get("when")),
    )
