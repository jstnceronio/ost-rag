from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser

from app.confluence.models import ConfluencePage
from app.processing.models import ParsedDocument


def _normalize_inline(text: str) -> str:
    text = unescape(text.replace("\xa0", " "))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return text.strip()


def _normalize_multiline(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in unescape(text).splitlines()]
    return "\n".join(line for line in lines if line.strip()).strip()


class _ConfluenceHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.heading_stack: list[str] = []
        self.sections: list[tuple[list[str], str]] = []
        self.blocks: list[str] = []

        self._heading_level: int | None = None
        self._heading_parts: list[str] = []
        self._paragraph_parts: list[str] = []
        self._list_stack: list[str] = []
        self._list_item_parts: list[str] = []
        self._in_list_item = False
        self._in_pre = False
        self._pre_parts: list[str] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._cell_parts: list[str] = []
        self._current_row: list[str] = []
        self._table_rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush_paragraph()
            self._flush_list_item()
            self._flush_table()
            self._flush_pre()
            self._heading_level = int(tag[1])
            self._heading_parts = []
            return

        if tag == "br":
            if self._in_pre:
                self._pre_parts.append("\n")
            elif self._in_list_item:
                self._list_item_parts.append("\n")
            elif self._in_cell:
                self._cell_parts.append("\n")
            else:
                self._paragraph_parts.append("\n")
            return

        if tag in {"p", "div"}:
            self._flush_paragraph()
            return

        if tag in {"ul", "ol"}:
            self._flush_paragraph()
            self._list_stack.append("-")
            return

        if tag == "li":
            self._flush_list_item()
            self._in_list_item = True
            self._list_item_parts = []
            return

        if tag == "pre":
            self._flush_paragraph()
            self._flush_list_item()
            self._flush_table()
            self._in_pre = True
            self._pre_parts = []
            return

        if tag == "table":
            self._flush_paragraph()
            self._flush_list_item()
            self._flush_pre()
            self._in_table = True
            self._table_rows = []
            return

        if tag == "tr":
            self._in_row = True
            self._current_row = []
            return

        if tag in {"th", "td"}:
            self._in_cell = True
            self._cell_parts = []
            return

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._heading_level is not None:
            heading = _normalize_inline("".join(self._heading_parts))
            if heading:
                self.heading_stack = self.heading_stack[: self._heading_level - 1]
                self.heading_stack.append(heading)
                self.blocks.append(f'{"#" * self._heading_level} {heading}')
            self._heading_level = None
            self._heading_parts = []
            return

        if tag in {"p", "div"}:
            self._flush_paragraph()
            return

        if tag == "li":
            self._flush_list_item()
            self._in_list_item = False
            return

        if tag in {"ul", "ol"}:
            self._flush_list_item()
            if self._list_stack:
                self._list_stack.pop()
            return

        if tag == "pre":
            self._flush_pre()
            self._in_pre = False
            return

        if tag in {"th", "td"}:
            cell_text = _normalize_multiline("".join(self._cell_parts))
            self._current_row.append(cell_text)
            self._cell_parts = []
            self._in_cell = False
            return

        if tag == "tr":
            if self._current_row:
                self._table_rows.append(self._current_row)
            self._current_row = []
            self._in_row = False
            return

        if tag == "table":
            self._flush_table()
            self._in_table = False
            return

    def handle_data(self, data: str) -> None:
        if self._heading_level is not None:
            self._heading_parts.append(data)
        elif self._in_pre:
            self._pre_parts.append(data)
        elif self._in_cell:
            self._cell_parts.append(data)
        elif self._in_list_item:
            self._list_item_parts.append(data)
        else:
            self._paragraph_parts.append(data)

    def close(self) -> None:
        super().close()
        self._flush_paragraph()
        self._flush_list_item()
        self._flush_pre()
        self._flush_table()

    def _add_section_block(self, text: str) -> None:
        if not text:
            return
        self.blocks.append(text)
        self.sections.append((self.heading_stack.copy(), text))

    def _flush_paragraph(self) -> None:
        text = _normalize_multiline("".join(self._paragraph_parts))
        self._paragraph_parts = []
        self._add_section_block(text)

    def _flush_list_item(self) -> None:
        if not self._in_list_item and not self._list_item_parts:
            return
        text = _normalize_multiline("".join(self._list_item_parts))
        self._list_item_parts = []
        if not text:
            return
        indent = "  " * max(len(self._list_stack) - 1, 0)
        bullet = self._list_stack[-1] if self._list_stack else "-"
        self._add_section_block(f"{indent}{bullet} {text}")

    def _flush_pre(self) -> None:
        text = _normalize_multiline("".join(self._pre_parts))
        self._pre_parts = []
        if text:
            self._add_section_block(f"```\n{text}\n```")

    def _flush_table(self) -> None:
        if not self._table_rows:
            return
        lines = [" | ".join(cell for cell in row if cell) for row in self._table_rows]
        self._table_rows = []
        text = "\n".join(line for line in lines if line.strip())
        self._add_section_block(text)


def parse_confluence_page(page: ConfluencePage) -> ParsedDocument:
    parser = _ConfluenceHTMLParser()
    parser.feed(page.body_storage or "")
    parser.close()

    text_parts = [f"# {page.title}"]
    text_parts.extend(block for block in parser.blocks if block)
    text = "\n\n".join(text_parts).strip()

    return ParsedDocument(
        doc_id=page.id,
        title=page.title,
        url=page.url,
        text=text,
        sections=parser.sections,
        metadata={
            "url": page.url,
            "space_id": page.space_id,
            "parent_id": page.parent_id,
            "status": page.status,
            "version": page.version,
            "created_at": page.created_at,
            "updated_at": page.updated_at,
        },
    )
