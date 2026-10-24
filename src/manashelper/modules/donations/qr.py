from collections import OrderedDict

from aiogram import Bot
from aiogram.types import FSInputFile, Message

from manashelper.modules.donations.catalog import DonationBank
from manashelper.services.html_sanitization import escape_html

MAX_CACHED_FILE_IDS = 32


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
