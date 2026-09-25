import json
from pathlib import Path
from typing import TypedDict, cast

from aiogram.types import BotCommand

from manashelper.localization.locale import Locale


class _CommandConfig(TypedDict):
    command: str
    description: dict[str, str]


# .../src/manashelper/services/bot_commands.py -> repo root is 3 parents up.
COMMANDS_DIR = Path(__file__).resolve().parents[3] / "docs" / "commands"


def _load_command_configs(filename: str) -> list[_CommandConfig]:
    """Reads `docs/commands/<filename>` fresh on every call, mirroring `services/version_history.py`."""
    return cast(list[_CommandConfig], json.loads((COMMANDS_DIR / filename).read_text(encoding="utf-8")))


def _build_commands(filename: str, locale: Locale) -> list[BotCommand]:
    return [
        BotCommand(command=config["command"], description=config["description"][locale.value])
        for config in _load_command_configs(filename)
    ]


def build_private_commands(locale: Locale) -> list[BotCommand]:
    return _build_commands("private.json", locale)


def build_group_commands(locale: Locale) -> list[BotCommand]:
    return _build_commands("group.json", locale)


def build_admin_commands(locale: Locale) -> list[BotCommand]:
    """Only ever registered against `BotCommandScopeChat(chat_id=Settings.admin_chat_id)`, not any
    of the "all chats" scopes - `/broadcast` shouldn't show up as a suggestion in every group the
    bot happens to be in, only in the one chat where it's actually authorized (see
    `bot/routers/broadcast.py::_is_admin_chat`)."""
    return _build_commands("admin.json", locale)
