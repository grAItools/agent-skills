"""JSON-file backed metric store."""

import json
from datetime import datetime
from pathlib import Path

DEFAULT_PATH = Path("metrics.json")


class Store:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add(self, name: str, value: float, timestamp: str | None = None) -> None:
        data = self.load()
        entries = data.setdefault(name, [])
        stamp = timestamp or datetime.now().strftime("%Y-%m-%d")
        entries.append({"date": stamp, "value": value})
        self.save(data)

    def daily_aggregate(self, name: str) -> dict:
        data = self.load()
        if name not in data:
            raise KeyError(name)
        result: dict[str, dict] = {}
        for entry in data[name]:
            bucket = result.setdefault(entry["date"], {"sum": 0.0, "count": 0})
            bucket["sum"] += entry["value"]
            bucket["count"] += 1
        for bucket in result.values():
            bucket["mean"] = bucket["sum"] / bucket["count"]
        return result
