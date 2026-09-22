from aiogram.utils.text_decorations import html_decoration


def escape_html(text: str) -> str:
    """Escapes `&`/`<`/`>` in arbitrary user-supplied text before it's interpolated into a message
    sent with `ParseMode.HTML` (the bot's default). Without this, a title/description/comment
    containing e.g. a bare `&` or `<tag>` makes Telegram reject the whole `sendMessage` call with
    "can't parse entities" - this is a correctness fix, not just a safety one."""
    return html_decoration.quote(text)
