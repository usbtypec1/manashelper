from manashelper.core.config import Settings
from manashelper.modules.ui_flows.infrastructure.rollout import RolloutRepository
from ui_flows.application.flows import FlowService
from ui_flows.domain.contracts import ContractIssue
from ui_flows.domain.rollout import RolloutMode, RolloutState
from ui_flows.errors import FlowNotFoundError, InvalidFlowError


class RolloutService:
    def __init__(self, repository: RolloutRepository, flows: FlowService, settings: Settings) -> None:
        self._repository, self._flows, self._settings = repository, flows, settings

    async def get(self) -> RolloutState:
        return await self._repository.get()

    async def allows(self, user_id: int, *, lock: bool = False) -> bool:
        state = await self._repository.get(lock=lock)
        return user_id > 0 and (
            state.mode == "all" or (state.mode == "admin" and user_id == self._settings.admin_chat_id)
        )

    async def active_count(self) -> int:
        return await self._repository.active_count()

    async def set(self, mode: RolloutMode, expected_revision: int, author_id: int) -> RolloutState:
        if mode == "all":
            for id in ("main_menu", "student_questions"):
                try:
                    draft = await self._flows.get(id)
                    if draft.published_version is None:
                        raise FlowNotFoundError
                    version = await self._flows.version(id, draft.published_version)
                    await self._flows.validate(version.document)
                except FlowNotFoundError as error:
                    raise InvalidFlowError(
                        [
                            ContractIssue(
                                code="rollout_not_ready",
                                path="/mode",
                                message="Publish main_menu and student_questions first",
                            )
                        ]
                    ) from error
        return await self._repository.set(mode, expected_revision, author_id)
