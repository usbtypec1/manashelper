import re
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup
from bs4.element import Tag

_DATE_PATTERN = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_CALORIES_PATTERN = re.compile(r"(\d+)")


class FoodMenuParseError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ScrapedDish:
    name: str
    photo_url: str
    calories: int


@dataclass(frozen=True, slots=True)
class ScrapedDailyMenu:
    date: date
    dishes: list[ScrapedDish]


def _parse_date(text: str) -> date:
    match = _DATE_PATTERN.search(text)
    if match is None:
        raise FoodMenuParseError(f"Could not parse date from {text!r}")
    day, month, year = match.groups()
    return date(int(year), int(month), int(day))


def _parse_dish(item: Tag) -> ScrapedDish:
    image = item.select_one("img")
    title = item.select_one("h5.item-title")
    subtitle = item.select_one("h6.item-subtitle")
    if image is None or title is None or subtitle is None:
        raise FoodMenuParseError("Dish card is missing an expected element")

    photo_url = image.get("src")
    if not isinstance(photo_url, str):
        raise FoodMenuParseError("Dish image is missing a src attribute")

    name = " ".join(title.get_text().split())
    calories_match = _CALORIES_PATTERN.search(subtitle.get_text())
    if calories_match is None:
        raise FoodMenuParseError(f"Could not parse calories from {subtitle.get_text()!r}")

    return ScrapedDish(name=name, photo_url=photo_url, calories=int(calories_match.group(1)))


class FoodMenuParser:
    def parse(self, html: str) -> list[ScrapedDailyMenu]:
        soup = BeautifulSoup(html, "lxml")
        containers = soup.select("div.container")
        if len(containers) < 2:
            raise FoodMenuParseError("Menu container not found")
        menu_container = containers[1]

        section_heads = menu_container.select("div.mbr-section-head")[1:]
        rows = menu_container.select("div.row.mt-2")
        if len(section_heads) != len(rows):
            raise FoodMenuParseError(f"Mismatched date headers ({len(section_heads)}) and dish rows ({len(rows)})")

        return [
            ScrapedDailyMenu(
                date=_parse_date(section_head.get_text()),
                dishes=[_parse_dish(item) for item in row.find_all("div", class_="item")],
            )
            for section_head, row in zip(section_heads, rows, strict=True)
        ]
