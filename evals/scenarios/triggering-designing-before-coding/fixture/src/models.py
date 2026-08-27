"""User model."""

from dataclasses import dataclass, field


@dataclass
class User:
    id: int
    name: str
    email: str
    address: str = ""
    phone: str = ""


USERS: dict[int, User] = {
    1: User(1, "Ada Lovelace", "ada@example.com", "12 St James's Square", "+44 20 7000 0001"),
    2: User(2, "Alan Turing", "alan@example.com", "78 High Street", "+44 20 7000 0002"),
}


def get_user(user_id: int) -> User | None:
    return USERS.get(user_id)
