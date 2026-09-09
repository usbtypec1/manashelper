import httpx

MENU_URL = "https://beslenme.manas.edu.kg/menu"


class FoodMenuClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http_client = http_client

    async def fetch_menu_html(self) -> str:
        response = await self._http_client.get(MENU_URL)
        response.raise_for_status()
        return response.text
