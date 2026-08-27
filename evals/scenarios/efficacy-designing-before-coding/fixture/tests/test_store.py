import json
import tempfile
import unittest
from pathlib import Path

from metrics_cli.store import Store


class StoreTest(unittest.TestCase):
    def test_add_and_aggregate(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(path=Path(tmp) / "metrics.json")
            store.add("deploys", 3, "2026-08-01")
            store.add("deploys", 5, "2026-08-01")
            store.add("deploys", 2, "2026-08-02")
            aggregate = store.daily_aggregate("deploys")
            self.assertEqual(aggregate["2026-08-01"], {"sum": 8.0, "count": 2, "mean": 4.0})
            self.assertEqual(aggregate["2026-08-02"], {"sum": 2.0, "count": 1, "mean": 2.0})
            data = json.loads((Path(tmp) / "metrics.json").read_text())
            self.assertEqual(len(data["deploys"]), 3)


if __name__ == "__main__":
    unittest.main()
