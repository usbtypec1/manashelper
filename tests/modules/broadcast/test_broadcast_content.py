import pytest

from manashelper.modules.broadcast.content import BroadcastButton, InvalidBroadcastButtonsError, parse_buttons


def test_buttons_preserve_links_callback_payloads_and_order():
    assert parse_buttons("Site | https://example.com/a?q=1\n\nМеню | callback:food_menu:0\nUser | tg://user?id=42") == [
        BroadcastButton("Site", url="https://example.com/a?q=1"),
        BroadcastButton("Меню", callback_data="food_menu:0"),
        BroadcastButton("User", url="tg://user?id=42"),
    ]


@pytest.mark.parametrize(
    "value",
    [
        "",
        "Name",
        " | https://example.com",
        "Name | callback:",
        "Name | javascript:alert(1)",
        "Name | https://",
        "Name | https://example.com/bad path",
        "Name | https://[",
        "Name | https://example.com:bad",
        "Name | callback:" + "я" * 33,
        "Name | callback:" + "x" * 65,
        "\n".join("Name | callback:ok" for _ in range(101)),
    ],
)
def test_invalid_buttons_are_rejected(value):
    with pytest.raises(InvalidBroadcastButtonsError):
        parse_buttons(value)


def test_callback_data_limit_is_measured_in_utf8_bytes():
    assert parse_buttons("Name | callback:" + "я" * 32)[0].callback_data == "я" * 32
