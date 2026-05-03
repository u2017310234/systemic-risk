# loc

This directory stores the G-SIB location cache.

## Files

- `gsib_branches.json`: single read-optimized JSON cache for branch data.

## Dynamic Maintenance

The branch cache should stay single-file for reads, but not be maintained manually.

Recommended operating model:

1. Keep `loc/gsib_branches.json` as the serving cache used by the frontend or API.
2. Refresh banks independently in the background instead of rebuilding the whole file on every request.
3. Use `stale-while-revalidate`: serve the current file immediately, then refresh outdated banks asynchronously.
4. Prefer official bank locator APIs when available.
5. Use OSM/Nominatim as the current low-friction fallback source and as a gap-filler.
6. Attach source metadata and `last_refreshed_at` to every bank or branch record so trust can be evaluated cheaply.

## Why This Is Low Latency

- Reads are O(1) file access against one local JSON file.
- Writes are incremental and bank-scoped.
- TTL prevents unnecessary refreshes.
- Source metadata supports selective revalidation instead of full rescans.

## Command

Refresh all banks:

```bash
python -m loc.branch_locator --force
```

Refresh one bank:

```bash
python -m loc.branch_locator --bank HSBC --force
```

Run the colocated tests:

```bash
pytest -q loc/test_branch_locator.py
```

## Next Upgrade

For production-quality branch maintenance, the preferred final architecture is:

- official locator adapters per bank
- bank-level refresh queue
- geocode normalization layer
- single-file cache export
- optional secondary index by `bank_id`, `country`, and `city`
