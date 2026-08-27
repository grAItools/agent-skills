"""HTTP route handlers (framework-free stubs)."""

import json

from src.models import USERS


def handle_get_users(query: dict | None = None) -> tuple[int, str]:
    query = query or {}
    results = [u.__dict__ for u in USERS.values()]
    return 200, json.dumps(results)


def handle_get_user(user_id: int) -> tuple[int, str]:
    from src.models import get_user

    user = get_user(user_id)
    if user is None:
        return 404, json.dumps({"error": "not found"})
    return 200, json.dumps(user.__dict__)
