# Supporting tools

Normal collection and app commands remain in the repository root. These tools
are separate from the production build:

| Location | Purpose |
| --- | --- |
| `ntvmr-bruno/` | Manual Bruno API request collection. Open its `bruno.json` in Bruno. Requests require a declared collection scope and budget. |
| `legacy/legacy_sync_ntvmr.py` | Original collector retained for reference; uses `requests` and the old SQLite workflow. It is not the central collection builder. |

Use the [bounded collection workflow](../docs/BOUNDED_WITNESS_DISCOVERY.md) for
current capture/import work and `python build_collection.py` to refresh app data.
Historical collector assumptions must not become scholarly assertions in the
active collection. Temporary tools and experiments belong in ignored
`data/.cache/`, not beside these maintained resources.
