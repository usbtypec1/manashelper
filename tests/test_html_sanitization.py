from manashelper.services.html_sanitization import escape_html


def test_escape_html_escapes_tags_and_ampersand() -> None:
    assert escape_html("<b>Fish & Chips</b>") == "&lt;b&gt;Fish &amp; Chips&lt;/b&gt;"


def test_escape_html_leaves_plain_text_untouched() -> None:
    assert escape_html("A normal title") == "A normal title"
