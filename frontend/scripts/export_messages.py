"""Export Mini App boot/error copy from the same catalogs as the bot."""

import json
from pathlib import Path

from babel.messages.pofile import read_po

from manashelper.platform.legal import TERMS_SOURCES, TERMS_UPDATED

ROOT = Path(__file__).resolve().parents[2]
messages = {}
for locale in ("en", "ru", "ky", "tr", "zh"):
    with (ROOT / f"src/manashelper/locales/{locale}/LC_MESSAGES/messages.po").open(encoding="utf-8") as stream:
        catalog = read_po(stream)
    messages[locale] = {
        str(message.id).removeprefix("gamification.ui."): message.string
        for message in catalog
        if isinstance(message.id, str) and message.id.startswith("gamification.ui.")
    }
    messages[locale]["preferences"] = {
        str(message.id).removeprefix("miniapp.ui."): message.string
        for message in catalog
        if isinstance(message.id, str) and message.id.startswith("miniapp.ui.")
    }
    messages[locale]["terms"] = {
        str(message.id).removeprefix("terms."): message.string
        for message in catalog
        if isinstance(message.id, str) and message.id.startswith("terms.")
    }
    messages[locale]["terms"]["sources"] = TERMS_SOURCES
    messages[locale]["terms"]["updated"] = TERMS_UPDATED
target = ROOT / "frontend/src/messages.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(messages, ensure_ascii=False) + "\n", encoding="utf-8")
