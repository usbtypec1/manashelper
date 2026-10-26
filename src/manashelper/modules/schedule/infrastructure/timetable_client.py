import httpx

TIMETABLE_URL_TEMPLATE = "http://timetable.manas.edu.kg/department-printer/{course_id}"


class TimetableClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http_client = http_client

    async def fetch_timetable_html(self, course_id: int) -> str:
        response = await self._http_client.get(TIMETABLE_URL_TEMPLATE.format(course_id=course_id))
        response.raise_for_status()
        return response.text
