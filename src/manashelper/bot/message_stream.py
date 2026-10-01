import asyncio
import logging
import secrets
from collections.abc import Awaitable
from contextlib import suppress

from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup, InputRichBlockUnion, InputRichMessage, Message

logger = logging.getLogger(__name__)
_PREVIEW_REFRESH_SECONDS = 20


class RichMessageStream:
    """Stream a private-chat preview and persist the completed response."""

    def __init__(self, message: Message, blocks: list[InputRichBlockUnion]) -> None:
        self._message = message
        self._blocks = list(blocks)
        self._draft_id = secrets.randbelow(2**31 - 1) + 1
        self._draft_enabled = True
        self._draft_started = False
        self._placeholder: Message | None = None

    def _content(self) -> InputRichMessage:
        return InputRichMessage(blocks=list(self._blocks), skip_entity_detection=True)

    async def start(self) -> None:
        await self._preview()

    async def _preview(self) -> None:
        if not self._draft_enabled:
            return
        bot = self._message.bot
        assert bot is not None
        try:
            await bot.send_rich_message_draft(
                chat_id=self._message.chat.id,
                message_thread_id=self._message.message_thread_id,
                draft_id=self._draft_id,
                rich_message=self._content(),
            )
            self._draft_started = True
        except TelegramAPIError:
            logger.warning("Rich message drafts unavailable; completing response normally", exc_info=True)
            self._draft_enabled = False
            if not self._draft_started:
                self._placeholder = await self._message.answer_rich(rich_message=self._content())

    async def load[T](self, result: Awaitable[T]) -> T:
        # Drafts expire after 30 seconds, so refresh the heading during a slow OBIS fetch.
        task = asyncio.ensure_future(result)
        try:
            while not task.done():
                done, _ = await asyncio.wait({task}, timeout=_PREVIEW_REFRESH_SECONDS)
                if not done:
                    await self._preview()
            return await task
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    async def append(self, blocks: list[InputRichBlockUnion]) -> None:
        self._blocks.extend(blocks)
        await self._preview()

    async def finish(self) -> None:
        if self._placeholder is not None:
            await self._placeholder.edit_text(rich_message=self._content(), parse_mode=None)
        else:
            await self._message.answer_rich(rich_message=self._content())

    async def finish_error(self, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
        if self._placeholder is not None:
            await self._placeholder.edit_text(text, reply_markup=reply_markup)
        else:
            await self._message.answer(text, reply_markup=reply_markup)
