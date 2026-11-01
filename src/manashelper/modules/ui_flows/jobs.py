import logging

from dishka import AsyncContainer

from ui_flows.application.maintenance import FlowMaintenanceService

logger = logging.getLogger(__name__)


async def cleanup_ui_flow_data_job(container: AsyncContainer) -> None:
    try:
        async with container() as request:
            cleared, deleted = await (await request.get(FlowMaintenanceService)).purge()
        logger.info("UI flow cleanup: %d closed payloads, %d screens", cleared, deleted)
    except Exception:
        logger.exception("UI flow cleanup failed")
