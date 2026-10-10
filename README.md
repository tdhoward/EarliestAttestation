# EarliestAttestation

Collect and visualize what scholarly sources report about the dates and verse
contents of Greek New Testament manuscripts. One central collection supports one
web app: [Attestation Explorer](web/attestation-explorer/index.html).

## Use the app

Run `npm start` from the repository, then open
<http://localhost:8000/web/attestation-explorer/>. Python 3 is the only server
dependency; the browser app uses plain HTML, CSS, and JavaScript.

The app automatically loads [data/attestations.json](data/attestations.json).
You can also open the HTML directly and select that JSON file when prompted;
browsers generally restrict automatic reads of neighboring files under `file://`.

Navigate the full New Testament timeline, zoom into a book, enter a verse, and
switch between the lower and upper endpoints of reported date ranges. Source
claims, complete date alternatives, unknown and contested states, and discovery
scope remain inspectable. Rankings describe up to five **earliest collected
witnesses per verse**, including when viewing a whole book.

## Find your way around

- [Repository guide](docs/README.md): documentation, commands, shared modules,
  and data ownership.
- [Development plan](docs/DEVELOPMENT_PLAN.md#next-development-work): current
  priorities and conditions for reopening work.
- [Source corroboration plan](docs/SOURCE_CORROBORATION_PLAN.md): agreed scope,
  retained findings, and the completed first-five review.
- [Explorer guide](docs/ATTESTATION_EXPLORER.md): controls, data format, and runtime.

## One collection, one app

| Location | Purpose |
| --- | --- |
| `data/collection.json` | Central source register, scholarly claims, and filters |
| `data/sources/`, `data/reference/` | Cited captures, coordinates, and API contracts |
| `data/discovery.json`, `data/source_checks.json` | Discovery scopes and scoped evidence checks |
| `data/attestations.json` | Derived data read by the app |
| `web/attestation-explorer/` | The maintained HTML/JS/CSS app |
| `pipeline/` | Shared Python implementation used by root command-line scripts |
| `tests/` | Offline regression tests and bounded fixtures |
| `tools/` | Manual API requests and the original legacy collector |
| `data/.cache/` | Ignored scratch, temporary databases, backups, and collection checkpoints |

After changing collected reports or scope, refresh the data:

```powershell
python build_collection.py
```

This offline command validates the registered captures, derives coverage and
rankings in a temporary database, and atomically replaces `data/attestations.json`.
`npm run data` is equivalent. Refresh the browser to see the result. Collection
updates do not generate HTML or additional datasets. See the
[build and memory contract](docs/ATTESTATION_EXPLORER.md#open-and-update).

## Source review and collection

The bounded omission sample and first-five extraction review have reached the
agreed stopping point. Independent comparisons remain deferred where unavailable;
one usable scholarly report is sufficient. See the
[current findings and reopening conditions](docs/SOURCE_CORROBORATION_PLAN.md#next-actions-and-verification).

Inspect or validate checks offline:

```powershell
python source_checks.py --details
python source_checks.py --check
```

The [source-check guide](docs/SOURCE_CHECKS.md) documents pending work, first-five
selection, queue refresh, and evidence rules. Deferred follow-up is distinct from
unreviewed work and does not authorize broader collection.

### Collect more data

All four declared catalogue inventories and eligible report capture are complete
for the retained snapshot. Broader collection remains deferred. The
[discovery guide](docs/BOUNDED_WITNESS_DISCOVERY.md) is the primary reference for
capture/import commands, date scope, budgets, pacing, blocked states, and recovery.
It documents both overnight catalogue capture and smaller book/range searches.

### Local API proxy

When direct NTVMR access is unavailable, use the owner's local API proxy.
The current address is `http://192.168.0.119:8889`; this is the only concrete
local proxy address kept in tracked files. `collect_catalogue.py collect --use-local-proxy`
reads this setting. If the address changes, update this one reference.

Replace `https://ntvmr.uni-muenster.de` with `<local proxy>` while preserving
endpoint paths and query parameters. Cite canonical NTVMR URLs. Permanent
captures use the placeholder; actual transport addresses belong in local commands
and ignored `data/.cache/` definitions and request caches. See the
[transport and access rules](docs/BOUNDED_WITNESS_DISCOVERY.md#central-collection-workflow).

## Scholarly scope

The project organizes published scholarship; it does not examine manuscripts.
Never determine contents, dates, hands, damage, or identity from manuscript images,
Greek transcription text, or apparatus interpretation. Prefer documented NTVMR
catalogue fields and explicit published assertions. Preserve the provider,
reported field or statement, citation, retrieval date, and qualifications.

Any reported surviving portion counts once for a witness/verse. Missing entries
are unknown; absence requires an explicit scholarly report. Incompatible explicit
reports are contested, retained, and deferred. Preserve complete competing date
intervals equally; never average, narrow, or merge endpoints. Count aliases or
joined fragments as one witness only when a source explicitly reports the identity.
Quotations and allusions in other works are outside the manuscript-copy corpus.

The reference axis uses provisional NA28 coordinates, retaining skipped traditional
verses as supplementary `omitted` coordinates. Default views exclude those verses;
bracketed passages have an independent collection filter. Edition status does not
determine manuscript contents. See [the source contract](docs/NTVMR_SOURCE_REPORT_CONTRACT.md),
[coordinate inventory](docs/NA28_INVENTORY.md), and [working rules](AGENTS.md).

## Development

Run commands from the repository root. The maintained Python code uses the
standard library; the app and Node tests need no npm package installation.

```powershell
python -m unittest discover -s tests
npm test
```

Use `python source_checks.py --check` for evidence validation and
`python build_na28_inventory.py --check` for coordinate validation when relevant.
`python build_collection.py --check` is a full offline rebuild and comparison
under the default 2 GiB memory ceiling. Use it for collection/export changes when
full verification is warranted; documentation edits and target selection do not
need a production rebuild.

Do not start servers or make live source requests as routine verification.
