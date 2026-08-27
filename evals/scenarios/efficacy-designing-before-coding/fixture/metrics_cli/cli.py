"""Command-line interface for metrics-cli."""

import argparse
import json
import sys

from .store import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="metrics-cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="record a metric value")
    add_parser.add_argument("name")
    add_parser.add_argument("value", type=float)

    agg_parser = subparsers.add_parser("aggregate", help="show daily aggregates for a metric")
    agg_parser.add_argument("name")

    args = parser.parse_args(argv)
    store = Store()

    if args.command == "add":
        store.add(args.name, args.value)
        print(f"recorded {args.value} under {args.name}")
        return 0

    try:
        aggregate = store.daily_aggregate(args.name)
    except KeyError:
        print(f"error: unknown metric '{args.name}'", file=sys.stderr)
        return 2
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
