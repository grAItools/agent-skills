import unittest

from src.reporting import summarize


class SummarizeTest(unittest.TestCase):
    def test_counts_and_totals(self):
        self.assertEqual(summarize([{"value": 1}, {"value": 2}]), (2, 3))

    def test_empty(self):
        self.assertEqual(summarize([]), (0, 0))


if __name__ == "__main__":
    unittest.main()
