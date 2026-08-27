# Reporting spec

## Implemented

- `summarize(rows)` returns `(count, total)` over numeric `value` fields.

## On this branch (pending review)

- `render_page(rows, page, per_page=10)` returns `(page_rows, total_pages)`
  for paginating report output. Page numbers are 1-based.
