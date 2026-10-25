"""Babel extractor for command description keys stored outside Python modules."""

import json
from collections.abc import Collection, Iterator, Mapping
from typing import BinaryIO, cast


def extract_commands(
    fileobj: BinaryIO,
    keywords: Mapping[str, object],
    comment_tags: Collection[str],
    options: Mapping[str, str],
) -> Iterator[tuple[int, str, str, list[str]]]:
    commands = cast(list[dict[str, str]], json.load(fileobj))
    for index, command in enumerate(commands, start=1):
        yield index, "gettext", command["description"], []
