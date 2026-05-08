from app.processing.attachments import parse_confluence_attachment
from tests.conftest import make_confluence_attachment


class TestParseConfluenceAttachment:
    def test_text_attachment_becomes_document(self):
        doc = parse_confluence_attachment(make_confluence_attachment(content=b"Deployment notes"))

        assert doc is not None
        assert doc.doc_id == "123:attachment:att1"
        assert doc.title == "notes.txt"
        assert "Deployment notes" in doc.text
        assert doc.metadata["source_type"] == "attachment"
        assert doc.metadata["parent_id"] == "123"

    def test_html_attachment_is_skipped(self):
        attachment = make_confluence_attachment(
            title="page.html",
            media_type="text/html",
            content=b"<html><body><h1>Heading</h1><p>Hello <b>world</b></p></body></html>",
        )

        assert parse_confluence_attachment(attachment) is None

    def test_unsupported_binary_attachment_is_skipped(self):
        attachment = make_confluence_attachment(
            title="image.png",
            media_type="image/png",
            content=b"\x89PNG\r\n",
        )

        assert parse_confluence_attachment(attachment) is None
