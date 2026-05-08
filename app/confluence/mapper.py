from __future__ import annotations
from datetime import datetime
from typing import Any

from app.confluence.models import ConfluenceAttachment, ConfluencePage


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


def _absolute_url(url: str | None, base_url: str) -> str | None:
    if url and not url.startswith("http"):
        base_path = base_url.rstrip("/").split("://", 1)[-1].split("/", 1)
        configured_context = f"/{base_path[1]}" if len(base_path) > 1 else ""
        if configured_context and url.startswith(f"{configured_context}/"):
            origin = base_url.removesuffix(configured_context)
            return f"{origin}{url}"
        return f"{base_url}{url}"
    return url


def map_attachment(
    payload: dict[str, Any],
    *,
    base_url: str,
    page_id: str,
    page_title: str,
    content: bytes,
) -> ConfluenceAttachment:
    links = payload.get("_links", {})
    version = payload.get("version", {})
    metadata = payload.get("metadata", {})
    extensions = payload.get("extensions", {})

    return ConfluenceAttachment(
        id=str(payload["id"]),
        title=payload.get("title", ""),
        page_id=str(payload.get("pageId") or page_id),
        page_title=page_title,
        media_type=payload.get("mediaType") or metadata.get("mediaType") or extensions.get("mediaType"),
        file_size=payload.get("fileSize") or extensions.get("fileSize"),
        url=_absolute_url(payload.get("webuiLink") or links.get("webui"), base_url),
        download_url=_absolute_url(payload.get("downloadLink") or links.get("download"), base_url),
        version=version.get("number"),
        created_at=_parse_datetime(payload.get("createdAt")),
        updated_at=_parse_datetime(version.get("createdAt") or version.get("when")),
        content=content,
    )
