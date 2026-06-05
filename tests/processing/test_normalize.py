from datetime import datetime
import pytest
from app.processing.normalize import _normalize_inline, _normalize_multiline, parse_confluence_page
from app.confluence.models import ConfluencePage


def _page(body: str, **kwargs) -> ConfluencePage:
    return ConfluencePage(
        id="1",
        title="Test Page",
        space_id="S1",
        parent_id=None,
        status="current",
        url="https://wiki.example.com/pages/1",
        body_storage=body,
        version=2,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 6, 1),
    )


class TestNormalizeInline:
    def test_replaces_nbsp(self):
        assert _normalize_inline("hello\xa0world") == "hello world"

    def test_collapses_multiple_spaces(self):
        assert _normalize_inline("hello    world") == "hello world"

    def test_strips_whitespace(self):
        assert _normalize_inline("  hello  ") == "hello"

    def test_unescapes_html_entities(self):
        assert _normalize_inline("&amp; &lt; &gt;") == "& < >"

    def test_empty_string(self):
        assert _normalize_inline("") == ""


class TestNormalizeMultiline:
    def test_preserves_newlines(self):
        result = _normalize_multiline("line1\nline2")
        assert "line1" in result
        assert "line2" in result

    def test_removes_blank_lines(self):
        result = _normalize_multiline("line1\n\n\nline2")
        assert "\n\n" not in result

    def test_collapses_inline_spaces(self):
        result = _normalize_multiline("  hello   world  ")
        assert result == "hello world"


class TestParseConfluencePage:
    def test_title_included_in_text(self):
        doc = parse_confluence_page(_page("<p>Content</p>"))
        assert "Test Page" in doc.text

    def test_simple_paragraph(self):
        doc = parse_confluence_page(_page("<p>Hello world</p>"))
        assert "Hello world" in doc.text
        assert len(doc.sections) == 1

    def test_empty_body(self):
        doc = parse_confluence_page(_page(""))
        assert doc.text == "# Test Page"
        assert doc.sections == []

    def test_heading_creates_section(self):
        doc = parse_confluence_page(_page("<h2>Setup</h2><p>Install the app</p>"))
        texts = [text for _, text in doc.sections]
        assert any("Install the app" in t for t in texts)

    def test_heading_path_tracked(self):
        doc = parse_confluence_page(_page("<h2>Setup</h2><p>Do this</p>"))
        heading_paths = [hp for hp, _ in doc.sections]
        assert any("Setup" in hp for hp in heading_paths)

    def test_list_items_included(self):
        doc = parse_confluence_page(_page("<ul><li>Item one</li><li>Item two</li></ul>"))
        assert "Item one" in doc.text
        assert "Item two" in doc.text

    def test_ordered_list_numbering_preserved(self):
        doc = parse_confluence_page(_page("<ol><li>Open settings</li><li>Enable MFA</li></ol>"))
        assert "1. Open settings" in doc.text
        assert "2. Enable MFA" in doc.text

    def test_table_rows_included(self):
        doc = parse_confluence_page(_page("<table><tr><td>Cell A</td><td>Cell B</td></tr></table>"))
        assert "Cell A" in doc.text
        assert "Cell B" in doc.text

    def test_code_block_wrapped(self):
        doc = parse_confluence_page(_page("<pre>code here</pre>"))
        assert "```" in doc.text
        assert "code here" in doc.text

    def test_metadata_populated(self):
        doc = parse_confluence_page(_page("<p>text</p>"))
        assert doc.metadata["version"] == 2
        assert doc.metadata["space_id"] == "S1"
        assert doc.doc_id == "1"
        assert doc.url == "https://wiki.example.com/pages/1"

    def test_br_tag_produces_newline(self):
        doc = parse_confluence_page(_page("<p>line1<br/>line2</p>"))
        assert "line1" in doc.text
        assert "line2" in doc.text
