# Requirements: bulk export (AGREED)

Status: signed off. Do not reopen scope.

## Need
Administrators need to download a complete archive of all records in one
operation, instead of paginating through the API.

## Agreed behavior
1. New endpoint: `POST /export` returns a streaming archive of every record.
2. Format is JSON lines (one record per line) inside the archive.
3. Long-running: the endpoint must stream, not buffer the whole dataset.
4. Failures midway leave no partial file on the client side.
5. No new dependencies.
