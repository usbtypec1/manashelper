import secrets
from uuid import UUID

from ui_flows.domain.delivery import Screen, ScreenButton, ScreenDelivery
from ui_flows.domain.state import ACTIVE_STATUSES, DialogState, ExecutionResult, RuntimeUser
from ui_flows.errors import InvalidEventError, StaleEventError
from ui_flows.ports.repositories import DeliveryStore, DialogStore


class ScreenDeliveryService:
    def __init__(self, deliveries: DeliveryStore, dialogs: DialogStore) -> None:
        self._deliveries = deliveries
        self._dialogs = dialogs

    async def prepare(
        self, result: ExecutionResult, screen: Screen, update_id: int | None, *, operation_id: UUID | None = None
    ) -> ScreenDelivery:
        if (update_id is None) == (operation_id is None):
            raise InvalidEventError("A screen requires one update or external operation identity")
        if update_id is not None:
            existing = await self._deliveries.by_update(update_id)
        else:
            assert operation_id is not None
            existing = await self._deliveries.by_operation(operation_id)
        if existing is not None:
            return existing
        delivery = ScreenDelivery(
            secrets.token_urlsafe(12),
            result.state.id,
            result.state.revision,
            update_id,
            result.state.chat_id,
            screen,
            "pending",
            None,
            operation_id,
        )
        await self._deliveries.create(delivery)
        return delivery

    async def callback(
        self, token: str, index: int, message_id: int, user: RuntimeUser
    ) -> tuple[DialogState, ScreenButton]:
        delivery = await self._deliveries.get(token)
        if delivery is None or delivery.chat_id != user.chat_id or delivery.status not in {"sent", "unknown"}:
            raise StaleEventError("Screen is unavailable")
        state = await self._dialogs.get(delivery.session_id)
        if state.user_id != user.id or state.revision != delivery.revision or state.status not in ACTIVE_STATUSES:
            raise StaleEventError("Screen is no longer current")
        if delivery.message_id is not None and delivery.message_id != message_id:
            raise InvalidEventError("The message does not belong to this screen")
        buttons = [button for row in delivery.screen.buttons for button in row]
        if delivery.screen.keyboard != "inline" or not 0 <= index < len(buttons) or buttons[index].url is not None:
            raise InvalidEventError("Invalid screen button")
        return state, buttons[index]

    async def reply_button(self, state: DialogState, text: str) -> ScreenButton | None:
        delivery = await self._deliveries.latest(state.id, state.revision)
        if delivery is None or delivery.screen.keyboard != "reply":
            return None
        return next((button for row in delivery.screen.buttons for button in row if button.label == text), None)

    async def claim(self, token: str) -> ScreenDelivery | None:
        delivery = await self._deliveries.get(token)
        if delivery is None:
            return None
        await self._dialogs.lock_chat(delivery.chat_id)
        delivery = await self._deliveries.get(token, lock=True)
        if delivery is None or delivery.status != "pending":
            return None
        state = await self._dialogs.get(delivery.session_id)
        active = await self._dialogs.active(delivery.chat_id)
        if state.revision != delivery.revision or (active is not None and active.id != state.id):
            await self._deliveries.set_status(token, "failed")
            return None
        # Persist an uncertain attempt BEFORE the network call. Never automatically resend it.
        await self._deliveries.set_status(token, "unknown")
        return delivery

    async def acknowledge(self, token: str, message_id: int | None, *, message_ids: tuple[int, ...] = ()) -> None:
        await self._deliveries.set_status(token, "sent", message_id, message_ids=message_ids)

    async def partial(self, token: str, message_ids: tuple[int, ...]) -> None:
        await self._deliveries.set_status(token, "unknown", message_ids=message_ids)

    async def reject(self, token: str) -> None:
        await self._deliveries.set_status(token, "failed")
