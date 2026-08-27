# Requirements: CSV export of daily aggregates (AGREED)

Status: signed off by product and engineering. Scope is settled; do not reopen.

## Need
Engineers want to pull `metrics-cli` aggregates into spreadsheets and BI tools.

## Agreed behavior
1. New CLI flag on the aggregate command: `--export-csv PATH`.
   When given, write the CSV file instead of printing JSON.
2. CSV schema, one row per day: `date,sum,count,mean`
   - `date`: ISO-8601 calendar date (`YYYY-MM-DD`)
   - `sum`: decimal sum of the metric's values that day
   - `count`: integer number of recorded values
   - `mean`: sum / count, two decimal places
3. Header row is always present.
4. One output file per metric invocation (the metric is the one being aggregated).
5. Errors (unknown metric, unwritable path) print to stderr and exit with code 2.
6. No new dependencies beyond the Python standard library.
