# Repository guide

Start with the root [README](../README.md) to run the app or refresh its data.
Use this guide to find implementation details and the document responsible for
each topic.

## Documentation map

| Topic | Primary document |
| --- | --- |
| Project boundaries and working rules | [AGENTS.md](../AGENTS.md) |
| Current priorities and acceptance criteria | [Development plan](DEVELOPMENT_PLAN.md#next-development-work) |
| Corroboration scope, findings, and stopping point | [Source corroboration plan](SOURCE_CORROBORATION_PLAN.md) |
| Check commands, schema, evidence pins, and recheck rules | [Scoped source checks](SOURCE_CHECKS.md) |
| Scholarly report admission and exact API field meanings | [NTVMR source contract](NTVMR_SOURCE_REPORT_CONTRACT.md) |
| Capture/import commands, budgets, recovery, and discovery states | [Bounded witness discovery](BOUNDED_WITNESS_DISCOVERY.md) |
| App behavior, browser format, build memory, and runtime | [Attestation Explorer](ATTESTATION_EXPLORER.md) |
| Verse coordinates and edition filters | [NA28 inventory](NA28_INVENTORY.md) |
| Frozen compatibility and pilot fixtures | [Fixture guide](../tests/fixtures/README.md) |

Update the primary document for a topic and link to it elsewhere. Keep current
priorities in the development plan, detailed corroboration outcomes in the
corroboration plan, and exact evidence in the collection registers and captures.
Use Git for software history rather than adding revision or milestone documents.

## Code map

Commands run from the repository root; shared implementation lives in the
`pipeline` Python package. No package installation is needed when
running these commands from the checkout.

| Entry point | Responsibility |
| --- | --- |
| `build_collection.py` | Offline validation, normalization, and atomic replacement of the app data |
| `source_checks.py` | Scoped evidence validation, first-five selection, and check queue maintenance |
| `build_na28_inventory.py` | Build or check the coordinate inventory |
| `collect_catalogue.py` | Bounded catalogue capture, status, and separate offline import |
| `collect_source_discovery.py` | Smaller declared book/range capture and data refresh |
| `sync_ntvmr.py` | Lower-level controlled SQLite collection commands |
| `export_attestation.py` | Offline export of scholarly batches or historical reviewed data |
| `audit_ntvmr.py`, `audit_reviewed.py` | Offline audits of older SQLite workflows |

The normal app build uses the scholarly-report path. Historical review tables
and their audit/export commands do not supply active app coverage.

| Shared module in `pipeline/` | Responsibility |
| --- | --- |
| `controlled_ntvmr.py` | NTVMR transport, parsers, SQLite infrastructure, reference mapping, and ranking primitives; also retains historical controlled commands |
| `source_discovery.py` | Bounded discovery contracts and date eligibility |
| `source_reports.py` | Scholarly claims, provenance, date alternatives, and coverage derivation |
| `report_explorer.py` | Explorer projection, streaming packing, and bounded compatibility formats |
| `browser_format.py` | Current compact browser format and codecs |
| `build_storage.py` | Disposable record spooling and incremental hashes |
| `build_memory.py` | Operating-system build memory limits and measurements |

`web/attestation-explorer/` contains the single app: `app.js` handles loading and
interaction, `explorer.js` the model and charts, and `collection-format.js` the
compact format reader. The HTML and CSS are maintained independently of data.
Python tests cover collection and exports; Node tests cover the model and app.
Manual API requests and the original collector live under [tools/](../tools/README.md).

## Data flow and ownership

```text
bounded capture -> data/sources/ -> offline import -> data/collection.json
                                                  + data/discovery.json
data/reference/ + registered sources + data/source_checks.json
                         |
                  build_collection.py
                         |
                 data/attestations.json
                         |
              web/attestation-explorer/
```

| Location | How to maintain it |
| --- | --- |
| `data/collection.json` | Central document register, scholarly reports, admission rules, and filters |
| `data/discovery.json` | Declared discovery scopes and retained search evidence |
| `data/source_checks.json` | Exact comparison scopes, pinned evidence, outcomes, and follow-up; checks do not create coverage claims |
| `data/sources/` | Preserve cited captures, raw responses, hashes, retrieval metadata, and qualifications |
| `data/reference/` | Maintain cited coordinate inventories and captured API contracts |
| `data/attestations.json` | Rebuild with `python build_collection.py`; this is the single derived app input |
| `data/.cache/` | Ignored scratch, backups, temporary databases, and resumable collection checkpoints; never product inputs |
| `tests/fixtures/` | Bounded regression inputs and frozen compatibility snapshots; not a second collection |

Capture paths are evidence references. Do not rename or regroup source files
merely to tidy the tree. Preserve collection checkpoints until the associated
capture/import work is finished. Rebuild app data when claims or export behavior
change; documentation and scoped check selection do not require a full rebuild.
