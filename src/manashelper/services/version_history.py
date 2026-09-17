import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# .../src/manashelper/services/version_history.py -> repo root is 3 parents up.
VERSIONS_DIR = Path(__file__).resolve().parents[3] / "docs" / "versions"
VERSIONS_PER_PAGE = 10


@dataclass(frozen=True, slots=True)
class VersionSummary:
    version: str
    released_at: date


@dataclass(frozen=True, slots=True)
class VersionDetail:
    version: str
    released_at: date
    description: str


def _parse_summary(path: Path) -> VersionSummary | None:
    version, separator, iso_date = path.stem.partition("-")
    if not separator:
        return None
    try:
        released_at = date.fromisoformat(iso_date)
    except ValueError:
        return None
    return VersionSummary(version=version, released_at=released_at)


def _sort_key(summary: VersionSummary) -> tuple[int, ...]:
    return tuple(int(part) for part in summary.version.split("."))


def _list_all() -> list[VersionSummary]:
    """Scans `docs/versions/` fresh on every call — the changelog lives entirely on disk, never
    cached in memory, so a version file can be added/edited without restarting the bot."""
    if not VERSIONS_DIR.is_dir():
        return []
    summaries = (_parse_summary(path) for path in VERSIONS_DIR.glob("*.md"))
    return sorted((summary for summary in summaries if summary is not None), key=_sort_key, reverse=True)


def total_pages() -> int:
    return max(1, math.ceil(len(_list_all()) / VERSIONS_PER_PAGE))


def get_page(page: int) -> list[VersionSummary]:
    start = page * VERSIONS_PER_PAGE
    return _list_all()[start : start + VERSIONS_PER_PAGE]


def get_version(version: str) -> VersionDetail | None:
    """Reads a single version file's content on demand — called only when the user opens that
    specific version's detail screen, not when listing versions."""
    if not VERSIONS_DIR.is_dir():
        return None
    for path in VERSIONS_DIR.glob("*.md"):
        summary = _parse_summary(path)
        if summary is not None and summary.version == version:
            return VersionDetail(
                version=summary.version,
                released_at=summary.released_at,
                description=path.read_text(encoding="utf-8").strip(),
            )
    return None
