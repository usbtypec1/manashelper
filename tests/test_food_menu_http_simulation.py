import os
from datetime import date

import httpx
import pytest

from manashelper.modules.food_menu.infrastructure import food_menu_client as client_module
from manashelper.modules.food_menu.infrastructure.food_menu_parser import FoodMenuParser

SIMULATION_URL = os.getenv("FOOD_MENU_SIMULATION_URL")
pytestmark = pytest.mark.skipif(not SIMULATION_URL, reason="Optional local Postman food menu simulation")


@pytest.mark.parametrize("status", [200, 500])
async def test_real_http_client_and_parser_preserve_menu_contract(monkeypatch, status):
    monkeypatch.setattr(client_module, "MENU_URL", f"{SIMULATION_URL}/menu")
    async with httpx.AsyncClient(headers={"x-mock-slug": "food-menu", "x-fixture-status": str(status)}) as http:
        client = client_module.FoodMenuClient(http)
        if status == 500:
            with pytest.raises(httpx.HTTPStatusError) as error:
                await client.fetch_menu_html()
            assert error.value.response.status_code == 500
        else:
            menus = FoodMenuParser().parse(await client.fetch_menu_html())
            assert menus[0].date == date(2026, 10, 25)
            assert [(dish.name, dish.calories) for dish in menus[0].dishes] == [("Fixture Soup", 150)]
