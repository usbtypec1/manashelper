import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

TOKEN = "123456:development-placeholder"
SECRET = "fixture_webhook_secret_123456789012345"
USER_ID = 992001


def authorization(user_id=USER_ID, age=0, **extra):
    fields = {
        "auth_date": str(int(time.time()) - age),
        "user": json.dumps({"id": user_id, "first_name": "Fixture"}),
        **extra,
    }
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return "tma " + urlencode(fields)
