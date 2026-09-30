from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, Message

from manashelper.repositories.user_repository import UserRepository
from manashelper.services.html_sanitization import escape_html

REQUISITES_DIR = Path(__file__).resolve().parents[3] / "docs" / "requisites"
SUPPORTED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})
MAX_CACHED_FILE_IDS = 32


@dataclass(frozen=True)
class DonationBank:
    id: str
    name: str
    path: Path


def list_donation_banks() -> list[DonationBank]:
    if not REQUISITES_DIR.is_dir():
        return []
    banks = [
        DonationBank(id=sha256(path.name.encode("utf-8")).hexdigest()[:16], name=path.stem, path=path)
        for path in REQUISITES_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(banks, key=lambda bank: bank.name.casefold())


class DonationQrService:
    """Reuse Telegram file IDs while bounding the in-process cache with LRU eviction."""

    def __init__(self) -> None:
        self._file_ids: OrderedDict[tuple[str, int, int], str] = OrderedDict()

    async def send_bank_qr(self, bot: Bot, chat_id: int, bank: DonationBank) -> Message:
        stat = bank.path.stat()
        key = (bank.path.name, stat.st_mtime_ns, stat.st_size)
        caption = escape_html(bank.name)
        cached_id = self._file_ids.get(key)
        if cached_id is not None:
            self._file_ids.move_to_end(key)
            return await bot.send_photo(chat_id=chat_id, photo=cached_id, caption=caption)

        sent = await bot.send_photo(chat_id=chat_id, photo=FSInputFile(bank.path), caption=caption)
        if sent.photo:
            # A replaced QR gets a new cache key; discard its old entry immediately.
            for old_key in tuple(self._file_ids):
                if old_key[0] == bank.path.name:
                    del self._file_ids[old_key]
            self._file_ids[key] = sent.photo[-1].file_id
            if len(self._file_ids) > MAX_CACHED_FILE_IDS:
                self._file_ids.popitem(last=False)
        return sent


class DonationService:
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def other_users_count(self) -> int:
        return max(0, await self._user_repository.count() - 1)
