from app.confluence.auth import build_session
from app.confluence.errors import ConfluenceAPIError
from app.confluence.mapper import map_page
from app.confluence.models import ConfluencePage
from typing import Any


class ConfluenceClient:
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.session = build_session(api_token)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=60)
        if not resp.ok:
            raise ConfluenceAPIError(
                status_code=resp.status_code,
                message=resp.text,
                url=url,
            )
        return resp.json()

    def get_page(self, page_id: str, body_format: str = "storage") -> ConfluencePage:
        expand_value = f"body.{body_format},version,history,space"
        payload = self._get(
            f"/rest/api/content/{page_id}",
            params={"expand": f"{expand_value},ancestors"},
        )
        return map_page(payload, base_url=self.base_url, body_format=body_format)

    def get_pages_by_space_id(self, space_id: str, body_format: str = "storage", page_size: int = 100, limit: int | None = None) -> list[ConfluencePage]:
        expand_value = f"body.{body_format},version,history,space,ancestors"
        start = 0
        pages: list[ConfluencePage] = []

        while True:
            batch_size = page_size if limit is None else min(page_size, limit - len(pages))
            if batch_size <= 0:
                break

            payload = self._get(
                "/rest/api/content",
                params={
                    "spaceId": space_id,
                    "type": "page",
                    "limit": batch_size,
                    "start": start,
                    "expand": expand_value,
                },
            )
            results = payload.get("results", [])
            pages.extend(map_page(result, base_url=self.base_url, body_format=body_format) for result in results)

            if len(results) < batch_size or (limit is not None and len(pages) >= limit):
                break

            start += batch_size

        return pages
