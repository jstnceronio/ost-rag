from __future__ import annotations

class ConfluenceError(Exception):
    pass

class ConfluenceAPIError(ConfluenceError):
    def __init__(self, status_code: int, message: str, url: str):
        self.status_code = status_code
        self.message = message
        self.url = url
        super().__init__(f"Confluence API error {status_code} for {url}: {message}")