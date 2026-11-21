from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class BroadcastButton:
    text: str
    url: str | None = None
    callback_data: str | None = None


class InvalidBroadcastButtonsError(ValueError):
    pass


def parse_buttons(text: str) -> list[BroadcastButton]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or len(lines) > 100:
        raise InvalidBroadcastButtonsError
    buttons = []
    for line in lines:
        label, separator, target = line.partition("|")
        label, target = label.strip(), target.strip()
        if not separator or not label or not target:
            raise InvalidBroadcastButtonsError
        if target.startswith("callback:"):
            data = target.removeprefix("callback:")
            if not 1 <= len(data.encode("utf-8")) <= 64:
                raise InvalidBroadcastButtonsError
            buttons.append(BroadcastButton(label, callback_data=data))
        else:
            try:
                url = urlsplit(target)
                valid = (
                    url.scheme in {"http", "https", "tg"}
                    and bool(url.netloc)
                    and not any(character.isspace() for character in target)
                )
                if url.scheme in {"http", "https"}:
                    valid = valid and bool(url.hostname) and url.port != 0
            except ValueError as error:
                raise InvalidBroadcastButtonsError from error
            if not valid:
                raise InvalidBroadcastButtonsError
            buttons.append(BroadcastButton(label, url=target))
    return buttons
