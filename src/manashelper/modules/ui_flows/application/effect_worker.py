"""Claim durable operations before external I/O and recover only their saved results."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID

from dishka import AsyncContainer

from manashelper.modules.ui_flows.infrastructure.deliveries import DeliveryRepository
from manashelper.modules.ui_flows.infrastructure.effects import EffectRepository
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.i18n.request import catalog_request
from manashelper.platform.i18n.service import TextCatalogService
from manashelper.platform.secrets import SecretCodec, SecretUnavailableError
from ui_flows.application.delegates import ExternalDelegateRegistry
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.domain.contracts import DelegateContext
from ui_flows.domain.effects import ExternalOperation
from ui_flows.domain.state import RuntimeUser
from ui_flows.errors import DialogNotFoundError
from ui_flows.ports.repositories import DialogStore

logger = logging.getLogger(__name__)


class EffectWorker:
    def __init__(self, container: AsyncContainer, registry: ExternalDelegateRegistry, codec: SecretCodec) -> None:
        self._container, self._registry, self._codec = container, registry, codec
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._closed = False

    async def _current(self, request: AsyncContainer, operation: ExternalOperation) -> bool:
        dialogs = await request.get(DialogService)
        user = RuntimeUser(operation.user_id, operation.chat_id)
        try:
            active = await dialogs.active(user)
            state = await dialogs.get(operation.session_id, user)
        except DialogNotFoundError:
            return False
        return active is not None and active.id == state.id and operation.matches_position(state, suspended=True)

    async def _secrets(
        self, repository: EffectRepository, operation: ExternalOperation, encrypted: dict[str, tuple[UUID, str]]
    ) -> None:
        definition = self._registry.definition(operation.delegate_id, operation.contract_version)
        for name, parameter in definition.inputs.items():
            if parameter.type != "secret" or operation.arguments.get(name) is None:
                continue
            handle = operation.arguments[name]
            if not isinstance(handle, str):
                raise SecretUnavailableError
            try:
                secret_id = UUID(handle)
            except ValueError:
                raise SecretUnavailableError from None
            ciphertext = await repository.get_secret(
                secret_id,
                operation.session_id,
                operation.user_id,
                operation.chat_id,
                datetime.now(UTC),
            )
            if ciphertext is None:
                raise SecretUnavailableError
            encrypted[name] = (secret_id, ciphertext)

    @staticmethod
    async def _remove(repository: EffectRepository, consumed: Iterable[UUID]) -> None:
        for secret_id in set(consumed):
            await repository.remove_secret(secret_id)

    async def _fail(self, operation_id: UUID, error_code: str, consumed: Iterable[UUID]) -> None:
        async with catalog_request(self._container) as request:
            repository = await request.get(EffectRepository)
            await repository.fail(operation_id, error_code)
            await self._remove(repository, consumed)

    async def run(self, operation_id: UUID) -> ExternalOperation | None:
        encrypted: dict[str, tuple[UUID, str]] = {}
        async with catalog_request(self._container) as request:
            repository = await request.get(EffectRepository)
            operation = await repository.get(operation_id)
            if operation is None:
                return None
            if operation.status == "succeeded":
                return operation
            if operation.status == "applied":
                delivery = await (await request.get(DeliveryRepository)).by_operation(operation_id)
                return operation if delivery is not None and delivery.status == "pending" else None
            if operation.status != "pending":
                return None
            await (await request.get(DialogStore)).lock_chat(operation.chat_id)
            current = await self._current(request, operation)
            claimed = await repository.claim(operation_id)
            if claimed is None:
                return None
            if not current:
                await repository.fail(operation_id, "cancelled")
                try:
                    await self._secrets(repository, claimed, encrypted)
                except Exception as error:
                    logger.warning("External operation cleanup unavailable (%s)", type(error).__name__)
                await self._remove(repository, (secret_id for secret_id, _ in encrypted.values()))
                return None
            try:
                self._registry.validate_arguments(claimed.delegate_id, claimed.contract_version, claimed.arguments)
                await self._secrets(repository, claimed, encrypted)
                version = await (await request.get(FlowService)).version(claimed.flow_id, claimed.flow_version)
                snapshot = await (await request.get(TextCatalogService)).version(version.text_catalog_release or 1)
                locale = await (await request.get(LocaleService)).get_locale(claimed.user_id)
                theme = await (await request.get(ThemeService)).get_theme(claimed.user_id)
            except SecretUnavailableError:
                await repository.fail(operation_id, "secret_unavailable")
                await self._remove(repository, (secret_id for secret_id, _ in encrypted.values()))
                return None
            except Exception as error:
                logger.warning("External operation preparation failed (%s)", type(error).__name__)
                await repository.fail(operation_id, "execution_failed")
                await self._remove(repository, (secret_id for secret_id, _ in encrypted.values()))
                return None
        # The unknown marker and all REQUEST finalizers commit before secrets or external handlers run.
        consumed = tuple(secret_id for secret_id, _ in encrypted.values())
        plaintext: dict[str, str] = {}
        try:
            for name, (secret_id, ciphertext) in encrypted.items():
                plaintext[name] = self._codec.decrypt(
                    ciphertext, secret_id, claimed.session_id, claimed.user_id, claimed.chat_id
                )
            context = DelegateContext(
                claimed.user_id,
                claimed.chat_id,
                str(claimed.session_id),
                str(claimed.id),
                secrets=plaintext,
                locale=locale.value,
                theme=theme.value,
            )
            with i18n.context(), i18n.use_catalog(snapshot), i18n.use_locale(locale.value), i18n.use_theme(theme):
                result = await self._registry.execute(
                    claimed.delegate_id, claimed.contract_version, context, claimed.arguments, external=True
                )
        except SecretUnavailableError:
            await self._fail(operation_id, "secret_unavailable", consumed)
            return None
        except Exception as error:
            logger.warning("External operation execution failed (%s)", type(error).__name__)
            await self._fail(operation_id, "execution_failed", consumed)
            return None
        finally:
            plaintext.clear()
        async with catalog_request(self._container) as request:
            repository = await request.get(EffectRepository)
            completed = await repository.complete(operation_id, result)
            await self._remove(repository, consumed)
            return await repository.get(operation_id) if completed else None

    async def run_forever(self, on_result: Callable[[UUID], Awaitable[None]]) -> None:
        while not self._closed:
            self._wake.clear()
            try:
                async with catalog_request(self._container) as request:
                    repository = await request.get(EffectRepository)
                    await repository.purge_expired(datetime.now(UTC))
                    operations = await repository.pending(limit=100)
                for operation_id in operations:
                    try:
                        result = await self.run(operation_id)
                        if result is not None:
                            await on_result(result.id)
                    except Exception as error:
                        logger.warning("External operation processing failed (%s)", type(error).__name__)
            except Exception as error:
                logger.warning("External operation polling failed (%s)", type(error).__name__)
            with suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=5)

    def start(self, on_result: Callable[[UUID], Awaitable[None]]) -> None:
        if self._closed:
            raise RuntimeError("Effect worker is closed")
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run_forever(on_result), name="ui-flow-effects")

    def notify(self) -> None:
        if not self._closed:
            self._wake.set()

    async def aclose(self) -> None:
        self._closed = True
        self._wake.set()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
