"""Read-only text snapshot consumed by the engine and its presentation adapters."""

from typing import Protocol

from ui_flows.domain.texts import TextEntry


class TextCatalog(Protocol):
    @property
    def release_id(self) -> int: ...

    @property
    def keys(self) -> frozenset[str]: ...

    def entry(self, key: str) -> TextEntry: ...

    def gettext(self, key: str, locale: str = "en", theme: str = "basic", n: int = 1) -> str: ...
