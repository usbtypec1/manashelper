import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from urllib.parse import urlencode


def signed_init_data(
    token: str,
    user_id: int,
    auth_date: int | None = None,
    fields: Mapping[str, str] | None = None,
) -> str:
    """Sign synthetic Mini App data using Telegram's documented two-stage HMAC."""
    values = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "query_id": "synthetic-test-query",
        "user": json.dumps({"id": user_id, "first_name": "Synthetic admin", "is_bot": False}, separators=(",", ":")),
        **(fields or {}),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)
