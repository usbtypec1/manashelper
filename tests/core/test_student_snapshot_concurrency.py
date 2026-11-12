import asyncio
import base64
import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from manashelper.modules.eders.application.models import EdersSnapshot
from manashelper.modules.eders.infrastructure.models.eders import EdersState
from manashelper.modules.eders.infrastructure.repositories.eders import EdersRepository
from manashelper.modules.eders.infrastructure.serialization import serialize_snapshot
from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.models.snapshot import ObisSnapshot
from manashelper.modules.obis.infrastructure.repositories.credentials import ObisCredentialsRepository
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.modules.users.queries import UsersQuery
from tests.modules.eders.application_factories import build_eders_service, build_eders_tracking_service
from tests.modules.obis.factories import build_obis


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
        credentials = ObisCredentialsQuery(ObisCredentialsRepository(session), crypto)
        if feature == "obis":
            service = build_obis(session, client, crypto)
            return service.grades.execute, service.results.get_exam_grades
        tracking = build_eders_tracking_service(
            EdersRepository(session), UsersQuery(UserRepository(session)), AsyncMock()
        )
        service = build_eders_service(credentials, client, tracking)
        return service.refresh_snapshot, service.get_snapshot

    try:
        async with sessions() as writer, sessions() as reader:
            client = AsyncMock()
            client.fetch_exam_grades_html.side_effect = slow_fetch
            client.fetch_snapshot.side_effect = slow_fetch
            refresh, _ = services(writer, client)
            _, read = services(reader, client)
            # Connect before the fetch starts so the timeout measures lock waiting, not connection setup.
            await reader.connection()
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
