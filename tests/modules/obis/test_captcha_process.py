import asyncio
import subprocess
import sys
from types import SimpleNamespace

import pytest

from manashelper.modules.obis.errors import ObisParseError
from manashelper.modules.obis.infrastructure import captcha
from manashelper.modules.obis.infrastructure.captcha import LocalCaptchaRecognizer

WORKER_CODE = "import json, sys, time; sys.stdin.buffer.read(); time.sleep(0.1); print(json.dumps('abcde'))"


@pytest.fixture
async def workers(monkeypatch):
    state = SimpleNamespace(code=WORKER_CODE, processes=[], peak=0, started=asyncio.Event())
    real_spawn = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        assert args[:3] == (sys.executable, "-m", captcha.WORKER_MODULE)
        process = await real_spawn(sys.executable, "-c", state.code, **kwargs)
        state.processes.append(process)
        state.peak = max(state.peak, sum(item.returncode is None for item in state.processes))
        state.started.set()
        return process

    monkeypatch.setattr(captcha.asyncio, "create_subprocess_exec", spawn)
    try:
        yield state
    finally:
        for process in state.processes:
            if process.returncode is None:
                process.kill()
            await process.wait()


def test_parent_adapter_does_not_import_the_solver_or_its_heavy_dependencies():
    code = (
        "import sys; "
        "from manashelper.modules.obis.infrastructure.captcha import LocalCaptchaRecognizer; "
        "assert 'numpy' not in sys.modules; "
        "assert 'PIL' not in sys.modules; "
        "assert 'manashelper.modules.obis.infrastructure.yii_captcha.solver' not in sys.modules"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


async def test_concurrent_requests_use_distinct_workers_one_at_a_time(workers):
    recognizer = LocalCaptchaRecognizer()
    tasks = [asyncio.create_task(recognizer.solve(b"image", 3347)) for _ in range(4)]
    ticks = 0
    while not all(task.done() for task in tasks):
        ticks += 1
        await asyncio.sleep(0.01)
    assert await asyncio.gather(*tasks) == ["abcde"] * 4
    assert workers.peak == 1
    assert len({process.pid for process in workers.processes}) == 4
    assert all(process.returncode == 0 for process in workers.processes)
    assert ticks > 4


async def test_cancelled_request_kills_and_reaps_worker_before_reusing_slot(workers):
    workers.code = "import sys, time; sys.stdin.buffer.read(); time.sleep(60)"
    recognizer = LocalCaptchaRecognizer()
    task = asyncio.create_task(recognizer.solve(b"image", 3347))
    await asyncio.wait_for(workers.started.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)
    assert workers.processes[0].returncode is not None
    workers.code = WORKER_CODE
    assert await recognizer.solve(b"next image", 3347) == "abcde"
    assert workers.peak == 1


async def test_timeout_stops_worker_and_becomes_a_temporary_obis_error(workers, monkeypatch):
    workers.code = "import sys, time; sys.stdin.buffer.read(); time.sleep(60)"
    monkeypatch.setattr(captcha, "WORKER_TIMEOUT_SECONDS", 0.05)
    with pytest.raises(ObisParseError, match="timed out"):
        await LocalCaptchaRecognizer().solve(b"image", 3347)
    assert workers.processes[0].returncode is not None


async def test_worker_failure_releases_the_slot_and_does_not_return_an_answer(workers):
    workers.code = "import sys; sys.exit(7)"
    recognizer = LocalCaptchaRecognizer()
    with pytest.raises(ObisParseError, match="status 7"):
        await recognizer.solve(b"image", 3347)
    workers.code = "print('null')"
    assert await recognizer.solve(b"next image", 3347) is None
    assert workers.peak == 1


@pytest.mark.parametrize("output", ["not-json", "123", "{}", "[]", '"ABCDE"', '"abc"', '"12345"'])
async def test_invalid_worker_response_is_not_used_as_a_captcha_answer(workers, output):
    workers.code = f"print({output!r})"
    with pytest.raises(ObisParseError, match="invalid"):
        await LocalCaptchaRecognizer().solve(b"image", 3347)


async def test_start_failure_is_a_temporary_obis_error(monkeypatch):
    async def fail(*args, **kwargs):
        raise OSError("synthetic launch failure")

    monkeypatch.setattr(captcha.asyncio, "create_subprocess_exec", fail)
    with pytest.raises(ObisParseError, match="could not start"):
        await LocalCaptchaRecognizer().solve(b"image", 3347)


async def test_repeated_cancellation_waits_for_worker_exit_before_next_request(monkeypatch):
    killed, waiting, reaped = asyncio.Event(), asyncio.Event(), asyncio.Event()
    launches = []

    class Process:
        returncode = None

        async def communicate(self, image):
            await asyncio.Event().wait()

        def kill(self):
            killed.set()

        async def wait(self):
            waiting.set()
            await reaped.wait()
            self.returncode = -9
            return self.returncode

    process = Process()

    async def spawn(*args, **kwargs):
        launches.append(process)
        return process

    monkeypatch.setattr(captcha.asyncio, "create_subprocess_exec", spawn)
    recognizer = LocalCaptchaRecognizer()
    first = asyncio.create_task(recognizer.solve(b"image", 3347))
    await asyncio.sleep(0)
    first.cancel()
    await asyncio.wait_for(waiting.wait(), 5)
    assert killed.is_set()
    second = asyncio.create_task(recognizer.solve(b"next", 3347))
    first.cancel()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert len(launches) == 1
    assert not first.done()
    second.cancel()
    reaped.set()
    for task in (first, second):
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
    assert process.returncode == -9
