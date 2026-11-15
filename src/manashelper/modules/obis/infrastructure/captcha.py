import asyncio

from manashelper.modules.obis.infrastructure.yii_captcha.solver import InvalidCaptchaError, solve


class LocalCaptchaRecognizer:
    """Run the packaged solver outside the event loop, with bounded CPU concurrency."""

    def __init__(self) -> None:
        self._slots = asyncio.Semaphore(2)

    async def solve(self, image: bytes, expected_hash: int) -> str | None:
        async with self._slots:
            try:
                return await asyncio.to_thread(solve, image, expected_hash)
            except InvalidCaptchaError:
                return None
