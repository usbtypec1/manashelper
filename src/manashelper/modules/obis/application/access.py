import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import httpx

from manashelper.modules.obis.application.models import StoredObisAuthState
from manashelper.modules.obis.application.ports import AuthStateStore, CredentialsStore
from manashelper.modules.obis.application.sessions import ObisSessions
from manashelper.modules.obis.application.use_cases.auto_login_obis import AutoLoginObisUseCase
from manashelper.modules.obis.errors import (
    ObisLoginError,
    ObisManualLoginRequiredError,
    ObisParseError,
    ObisRetryLaterError,
    ObisSessionExpiredError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ObisAccessService:
    """Serialize access to one account and recover its session once per operation.

    Operations may raise ObisSessionExpiredError only before any external mutation.
    Their cookie mapping is in/out: authenticated responses may update it.
    Expected failures become outcomes the caller must catch inside its transaction,
    so retry state and a queued manual-login notice can commit together.
    """

    store: CredentialsStore
    sessions: ObisSessions
    auto_login: AutoLoginObisUseCase
    states: AuthStateStore

    async def with_session[T](self, user_id: int, operation: Callable[[dict[str, str]], Awaitable[T]]) -> T:
        await self.store.lock(user_id)
        state = await self.states.get(user_id)
        if state is not None:
            if state.manual_required:
                raise ObisManualLoginRequiredError
            if state.retry_at is not None and state.retry_at > datetime.now(UTC):
                raise ObisRetryLaterError
        try:
            cookies = await self.sessions.get_cookies(user_id)
        except ObisSessionExpiredError:
            cookies = await self._login(user_id)
        for attempt in range(2):
            previous = dict(cookies)
            try:
                try:
                    result = await operation(cookies)
                finally:
                    # A parser/downstream failure must not lose authenticated cookie rotation.
                    if cookies != previous:
                        await self.sessions.update_cookies(user_id, cookies)
            except ObisSessionExpiredError:
                if attempt:
                    await self._require_manual(user_id, "session_rejected")
                cookies = await self._login(user_id)
            except httpx.HTTPError:
                await self._defer(user_id, "transport")
            else:
                return result
        raise AssertionError("OBIS session retry was not resolved")

    async def record_refresh_success(self, user_id: int) -> None:
        await self.store.lock(user_id)
        state = await self.states.get(user_id)
        if state is not None and not state.manual_required:
            await self.states.delete(user_id)

    async def claim_manual_login_notice(self, user_id: int) -> bool:
        await self.store.lock(user_id)
        state = await self.states.get(user_id)
        if state is None or not state.manual_required or state.notified:
            return False
        await self.states.save(user_id, replace(state, notified=True))
        return True

    async def _login(self, user_id: int) -> dict[str, str]:
        try:
            captcha = await self.auto_login.execute(user_id)
        except ObisLoginError:
            await self._require_manual(user_id, "credentials")
        except (httpx.HTTPError, ObisParseError):
            await self._defer(user_id, "login_unavailable")
        else:
            if captcha is not None:
                await self._require_manual(user_id, "captcha")
            return await self.sessions.get_cookies(user_id)
        raise AssertionError("OBIS login failure was not resolved")

    async def _require_manual(self, user_id: int, reason: str) -> None:
        await self.sessions.expire(user_id)
        await self.states.save(user_id, StoredObisAuthState(True, reason))
        raise ObisManualLoginRequiredError

    async def _defer(self, user_id: int, reason: str) -> None:
        previous = await self.states.get(user_id)
        failures = (previous.failures if previous is not None else 0) + 1
        delay = timedelta(minutes=min(15 * 2 ** min(failures - 1, 5), 360))
        await self.states.save(user_id, StoredObisAuthState(False, reason, failures, datetime.now(UTC) + delay))
        logger.warning("OBIS access deferred for user %s: %s", user_id, reason)
        raise ObisRetryLaterError
