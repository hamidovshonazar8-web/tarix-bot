# -*- coding: utf-8 -*-
"""
Telegram Mini App yuboradigan `initData`ni tekshirish.
Bu — foydalanuvchi haqiqatan ham Telegram orqali kirganini tasdiqlash usuli
(hech kim o'zini boshqa foydalanuvchi sifatida ko'rsata olmasligi uchun).

Rasmiy algoritm: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400):
    """
    initData satrini tekshiradi. To'g'ri bo'lsa {"user": {...}, "auth_date": ...} qaytaradi,
    noto'g'ri yoki eskirgan bo'lsa None qaytaradi.
    """
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = parsed.get("auth_date")
    if auth_date and max_age_seconds:
        try:
            if time.time() - int(auth_date) > max_age_seconds:
                return None
        except ValueError:
            pass

    user = None
    if "user" in parsed:
        try:
            user = json.loads(parsed["user"])
        except json.JSONDecodeError:
            user = None

    return {"user": user, "auth_date": auth_date}
