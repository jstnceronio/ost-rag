from __future__ import annotations

import json
import mimetypes
import re
from io import BytesIO
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from app.confluence.models import ConfluenceAttachment
from app.processing.models import ParsedDocument
from app.processing.normalize import _normalize_multiline
from pypdf import PdfReader

_TEXT_MEDIA_TYPES = {
    "application/json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    "application/javascript",
    "application/sql",
    "application/csv",
    "application/rtf",
    "text/csv",
    "text/markdown",
    "text/plain",
    "text/xml",
    "text/x-python",
    "text/x-shellscript",
}

_TEXT_EXTENSIONS = {
    ".csv",
    ".json",
    ".log",
    ".md",
    ".rst",
    ".sql",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def parse_confluence_attachment(attachment: ConfluenceAttachment) -> ParsedDocument | None:
    text = _extract_attachment_text(attachment)
    if not text:
        return None

    title = attachment.title or f"Attachment {attachment.id}"
    section_text = "\n".join(
        part
        for part in (
            f"Attached to page: {attachment.page_title}",
            f"Filename: {title}",
            f"Media type: {attachment.media_type}" if attachment.media_type else None,
            "",
            text,
        )
        if part is not None
    ).strip()

    return ParsedDocument(
        doc_id=f"{attachment.page_id}:attachment:{attachment.id}",
        title=title,
        url=attachment.url or attachment.download_url,
        text=f"# {title}\n\n{section_text}",
        sections=[(["Attachment"], section_text)],
        metadata={
            "source_type": "attachment",
            "url": attachment.url or attachment.download_url,
            "parent_id": attachment.page_id,
            "parent_title": attachment.page_title,
            "attachment_id": attachment.id,
            "media_type": attachment.media_type,
            "file_size": attachment.file_size,
            "version": attachment.version,
            "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
            "updated_at": attachment.updated_at.isoformat() if attachment.updated_at else None,
        },
    )


def _extract_attachment_text(attachment: ConfluenceAttachment) -> str:
    media_type = (attachment.media_type or _guess_media_type(attachment.title) or "").lower()
    extension = _extension(attachment.title)

    if media_type in {"text/html", "application/xhtml+xml"} or extension in {".html", ".htm"}:
        return ""

    if media_type == "application/json" or extension == ".json":
        return _normalize_multiline(_json_to_text(attachment.content))

    if extension == ".docx" or media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _normalize_multiline(_docx_to_text(attachment.content))

    if media_type == "application/pdf" or extension == ".pdf":
        return _normalize_multiline(_pdf_to_text(attachment.content))

    if _is_text_attachment(media_type, extension):
        return _normalize_multiline(_decode_text(attachment.content))

    return ""


def _is_text_attachment(media_type: str, extension: str) -> bool:
    return media_type.startswith("text/") or media_type in _TEXT_MEDIA_TYPES or extension in _TEXT_EXTENSIONS


def _guess_media_type(title: str) -> str | None:
    media_type, _ = mimetypes.guess_type(title)
    return media_type


def _extension(title: str) -> str:
    match = re.search(r"(\.[A-Za-z0-9]+)$", title or "")
    return match.group(1).lower() if match else ""


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _json_to_text(content: bytes) -> str:
    raw = _decode_text(content)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def _docx_to_text(content: bytes) -> str:
    try:
        with ZipFile(BytesIO(content)) as archive:
            xml_content = archive.read("word/document.xml")
    except (BadZipFile, KeyError):
        return ""

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return ""

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        line = "".join(texts).strip()
        if line:
            paragraphs.append(line)

    return "\n".join(paragraphs)


def _pdf_to_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
