# metrics-cli

A tiny command-line tool for recording named numeric metrics and viewing daily
aggregates. Data lives in a single JSON file (`metrics.json`).

## Usage

```
python -m metrics_cli add deploys 3
python -m metrics_cli aggregate deploys
```
