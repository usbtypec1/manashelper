import asyncio
import json
import sys
from contextlib import suppress

from manashelper.modules.obis.errors import ObisParseError

WORKER_MODULE = "manashelper.modules.obis.infrastructure.captcha_worker"
WORKER_TIMEOUT_SECONDS = 60.0


async def stop_worker(process: asyncio.subprocess.Process) -> None:
    """Kill and reap a running worker before releasing the recognition slot."""
    if process.returncode is not None:
        return
    with suppress(ProcessLookupError):
        process.kill()
    waiter = asyncio.create_task(process.wait())
    cancelled = False
    while not waiter.done():
        try:
            await asyncio.shield(waiter)
        except asyncio.CancelledError:
            cancelled = True
    await waiter
    if cancelled:
        raise asyncio.CancelledError


class LocalCaptchaRecognizer:
    """Run one disposable solver process at a time; retain no glyph/search memory."""

    def __init__(self) -> None:
        self._slot = asyncio.Lock()

    async def solve(self, image: bytes, expected_hash: int) -> str | None:
        async with self._slot:
            try:
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    WORKER_MODULE,
                    str(expected_hash),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
            except OSError as error:
                raise ObisParseError("OBIS captcha worker could not start") from error
            try:
                try:
                    output, _ = await asyncio.wait_for(process.communicate(image), timeout=WORKER_TIMEOUT_SECONDS)
                except TimeoutError as error:
                    raise ObisParseError("OBIS captcha worker timed out") from error
            finally:
                await stop_worker(process)
            if process.returncode != 0:
                raise ObisParseError(f"OBIS captcha worker exited with status {process.returncode}")
            try:
                answer = json.loads(output)
            except ValueError as error:
                raise ObisParseError("OBIS captcha worker returned invalid output") from error
            if answer is None:
                return None
            if (
                isinstance(answer, str)
                and 5 <= len(answer) <= 6
                and answer.isascii()
                and answer.isalpha()
                and answer.islower()
            ):
                return answer
            raise ObisParseError("OBIS captcha worker returned an invalid answer")
