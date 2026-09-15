"""Provider-neutral structural ports for workflow integrations."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class JsonRecordStore(Protocol):
    def load(self, path: str | Path) -> Any: ...
    def publish(self, path: str | Path, value: Any) -> Path: ...


@runtime_checkable
class ImagePublisher(Protocol):
    def publish_png(self, root: str | Path, path: str | Path, image: Any) -> Path: ...


@runtime_checkable
class GenerationProvider(Protocol):
    """A provider adapter that returns a provider-neutral delivery or failure."""

    def invoke(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...


@runtime_checkable
class Clock(Protocol):
    def now_iso8601(self) -> str: ...
