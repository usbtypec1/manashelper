import asyncio
import base64
import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from manashelper.modules.eders.application.eders import EdersService
from manashelper.modules.eders.application.models import EdersSnapshot
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.infrastructure.orm import EdersState
from manashelper.modules.eders.infrastructure.repository import EdersRepository
from manashelper.modules.eders.infrastructure.serialization import serialize_snapshot
from manashelper.modules.obis.application.credentials import ObisCredentialsService
from manashelper.modules.obis.application.obis import ObisService
from manashelper.modules.obis.infrastructure.credentials_repository import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.snapshot import ObisSnapshot
from manashelper.modules.obis.infrastructure.snapshot_repository import ObisSnapshotRepository
from manashelper.modules.users.infrastructure.user import User
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.modules.users.queries import UsersQuery


@pytest.mark.parametrize("feature", ["obis", "eders"])
async def test_cached_reads_do_not_wait_for_background_http_fetch(engine, feature):
    user_id = 975301
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    encrypted = crypto.encrypt("password")
    now = datetime.now(UTC)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions.begin() as setup:
        setup.add(
            User(id=user_id, full_name="Concurrency test", student_number="student", encrypted_password=encrypted)
        )
        await setup.flush()
        setup.add(
            ObisSnapshot(
                user_id=user_id,
                kind="grades",
                credential_marker=hashlib.sha256(encrypted.encode()).hexdigest(),
                payload="[]",
                fetched_at=now,
            )
        )
        setup.add(
            EdersState(
                user_id=user_id,
                credential_marker=hashlib.sha256(b"student").hexdigest(),
                snapshot=serialize_snapshot(EdersSnapshot((), now)),
            )
        )

    entered, release = asyncio.Event(), asyncio.Event()

    async def slow_fetch(*args):
        entered.set()
        await release.wait()
        raise RuntimeError("simulated outage")

    def services(session, client):
        credentials = ObisCredentialsService(ObisCredentialsRepository(session), client, crypto)
        if feature == "obis":
            service = ObisService(credentials, client, ObisSnapshotRepository(session))
            return service.refresh_exam_grades, service.get_exam_grades
        tracking = EdersTrackingService(EdersRepository(session), UsersQuery(UserRepository(session)))
        service = EdersService(credentials, client, tracking)
        return service.refresh_snapshot, service.get_snapshot

    try:
        async with sessions() as writer, sessions() as reader:
            client = AsyncMock()
            client.fetch_exam_grades_html.side_effect = slow_fetch
            client.fetch_snapshot.side_effect = slow_fetch
            refresh, _ = services(writer, client)
            _, read = services(reader, client)
            task = asyncio.create_task(refresh(user_id))
            try:
                await asyncio.wait_for(entered.wait(), timeout=2)
                cached = await asyncio.wait_for(read(user_id), timeout=1)
                assert cached == ([] if feature == "obis" else EdersSnapshot((), now))
                assert not task.done()
            finally:
                release.set()
                with pytest.raises(RuntimeError, match="simulated outage"):
                    await task
                await writer.rollback()
    finally:
        async with sessions.begin() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
