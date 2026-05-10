from collections.abc import Iterator
from contextlib import contextmanager
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class TracingService:
    def __init__(self) -> None:
        self._enabled = (
            settings.langfuse_enabled
            and bool(settings.langfuse_public_key)
            and bool(settings.langfuse_secret_key)
        )
        self._client = None
        self._callback_handler_cls = None

        if not self._enabled:
            if settings.langfuse_enabled:
                missing = [
                    name
                    for name, value in {
                        "LANGFUSE_PUBLIC_KEY": settings.langfuse_public_key,
                        "LANGFUSE_SECRET_KEY": settings.langfuse_secret_key,
                    }.items()
                    if not value
                ]
                logger.warning(
                    "Langfuse tracing is enabled but missing required settings: %s",
                    ", ".join(missing),
                )
            return

        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        kwargs: dict[str, Any] = {
            "public_key": settings.langfuse_public_key,
            "secret_key": settings.langfuse_secret_key,
        }
        if settings.langfuse_base_url:
            kwargs["base_url"] = settings.langfuse_base_url

        self._client = Langfuse(**kwargs)
        self._callback_handler_cls = CallbackHandler
        logger.info("Langfuse tracing initialized")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def langchain_callback(self) -> Any | None:
        if not self._callback_handler_cls:
            return None
        return self._callback_handler_cls(public_key=settings.langfuse_public_key)

    def flush(self) -> None:
        if self._client:
            try:
                self._client.flush()
            except Exception:
                logger.exception("Failed to flush Langfuse traces")

    def shutdown(self) -> None:
        if self._client:
            try:
                self._client.shutdown()
            except Exception:
                logger.exception("Failed to shutdown Langfuse client")

    @contextmanager
    def span(
        self,
        name: str,
        *,
        input: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[Any | None]:
        if not self._client:
            yield None
            return

        with self._client.start_as_current_observation(
            as_type="span",
            name=name,
            input=input,
            metadata=metadata,
        ) as observation:
            yield observation

    def update(
        self,
        observation: Any | None,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if observation is None:
            return

        kwargs: dict[str, Any] = {}
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata

        if kwargs:
            observation.update(**kwargs)
