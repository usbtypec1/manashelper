from datetime import UTC, datetime, timedelta

from ui_flows.ports.repositories import MaintenanceStore


class FlowMaintenanceService:
    def __init__(self, repository: MaintenanceStore) -> None:
        self._repository = repository

    async def purge(self) -> tuple[int, int]:
        return await self._repository.purge_closed(datetime.now(UTC) - timedelta(days=7))
