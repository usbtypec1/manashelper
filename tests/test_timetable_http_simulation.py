import os

import httpx
import pytest

from manashelper.modules.schedule.infrastructure import timetable_client as client_module
from manashelper.modules.schedule.infrastructure.timetable_parser import parse_timetable_page

SIMULATION_URL = os.getenv("TIMETABLE_SIMULATION_URL")
pytestmark = pytest.mark.skipif(not SIMULATION_URL, reason="Optional local Postman timetable simulation")


@pytest.mark.parametrize("status", [200, 500])
async def test_timetable_client_and_parser_over_real_http(monkeypatch, status):
    monkeypatch.setattr(client_module, "TIMETABLE_URL_TEMPLATE", f"{SIMULATION_URL}/department-printer/{{course_id}}")
    async with httpx.AsyncClient(headers={"x-mock-slug": "timetable", "x-fixture-status": str(status)}) as http:
        client = client_module.TimetableClient(http)
        if status == 500:
            with pytest.raises(httpx.HTTPStatusError):
                await client.fetch_timetable_html(123)
        else:
            slots = parse_timetable_page(await client.fetch_timetable_html(123))
            assert [(slot.weekday, slot.time_range) for slot in slots] == [(1, "09:00-09:50")]
            assert slots[0].lessons[0].lesson_code == "CS101"
            assert slots[0].lessons[0].lesson_name == "Analysis"
