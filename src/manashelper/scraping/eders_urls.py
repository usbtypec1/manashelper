from urllib.parse import parse_qs, urljoin, urlsplit

EDERS_BASE_URL = "https://eders.manas.edu.kg"


class EdersUnsafeUrlError(Exception):
    """A link is outside the explicitly supported read-only endpoints."""


def safe_eders_url(href: str, paths: set[str]) -> str:
    url = urlsplit(urljoin(EDERS_BASE_URL, href))
    if url.scheme != "https" or url.netloc != "eders.manas.edu.kg" or url.path not in paths or url.fragment:
        raise EdersUnsafeUrlError("Unsupported eders URL")
    params = parse_qs(url.query, keep_blank_values=True)
    if set(params) != {"id"} or len(params["id"]) != 1:
        raise EdersUnsafeUrlError("Unsupported eders parameters")
    value = params["id"][0]
    if not value.isascii() or not value.isdecimal() or int(value) <= 0:
        raise EdersUnsafeUrlError("Invalid eders identifier")
    return f"{EDERS_BASE_URL}{url.path}?id={int(value)}"


def eders_id(url: str) -> int:
    return int(parse_qs(urlsplit(url).query)["id"][0])
