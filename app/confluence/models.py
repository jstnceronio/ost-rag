from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

@dataclass
class ConfluencePage:
    id: str
    title: str
    space_id: str | None
    parent_id: str | None
    status: str | None
    url: str | None
    body_storage: str
    version: int | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass
class ConfluenceAttachment:
    id: str
    title: str
    page_id: str
    page_title: str
    media_type: str | None
    file_size: int | None
    url: str | None
    download_url: str | None
    version: int | None
    created_at: datetime | None
    updated_at: datetime | None
    content: bytes
