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
scope remain inspectable. Rankings describe **earliest collected witnesses**.

## One collection, one app

| Location | Purpose |
| --- | --- |
| `data/collection.json` | Current document register, books, explicit additional reports, and filters |
| `data/sources/` | Scholarly source captures, including raw responses and retrieval metadata |
| `data/discovery.json` | Current independent bounded discovery scopes and search captures |
| `data/reference/` | Cited verse coordinates and API field contracts |
| `data/attestations.json` | Current derived data read by the app |
| `web/attestation-explorer/` | The single maintained HTML/JS/CSS app |
| `data/.cache/` | Ignored temporary databases, local scratch, and backups; never app inputs |

The source register and captures are the collection's inputs. The browser data
file is a reproducible view of those inputs. Tests have their own small regression
fixtures; they do not supply an alternate production collection.

After changing collected reports or scope, refresh the data:

```powershell
python build_collection.py
```

This offline command validates captures, derives exact reference mappings, computes
rankings in a temporary database, and replaces `data/attestations.json`. Refresh
the browser to see the result. It creates no HTML, book-specific export, persistent
replay database, or numbered revision file. `npm run data` is equivalent.

The current collection reuses 20 witnesses' retained reports across all
27 books, with 7,928 default graphable verses, 16,734 reported-present
witness/verse pairs, and 142,086 unknown pairs. Thirteen default coordinates have
no exact match in the retained contents reports and remain unknown. Unknown
includes missing reports for fragmentary witnesses; it does not mean absence.
Galatians, Hebrews, Ephesians, 1 Thessalonians, and 2 Thessalonians have completed
bounded indexed searches for IDs 10000–19999; discovery across the wider catalogue
remains incomplete. The 1 Thessalonians search reused P30 and P46, collected P61
and P65, and added 73 default presence pairs across seven books with five requests.
Scholarly citations use canonical NTVMR URLs. The owner-supplied local API proxy
is an access route, and TLS verification is not a collection prerequisite.

The app stores lossless version 3 JSON using shared records and exact sparse
coverage. It retains read-only data for charting and resolves complete observations
for the selected verse. Version 1/2 files remain supported through fetch and the
local file picker. See [the explorer documentation](docs/ATTESTATION_EXPLORER.md)
for storage, loading, and runtime behavior.

## Collect more data

`collect_source_discovery.py` conducts a declared, budgeted book/range search,
reuses existing document captures, saves new reports to `data/sources/`, updates
the central registers, and refreshes the app data. It does not generate charts.
See [bounded discovery](docs/BOUNDED_WITNESS_DISCOVERY.md) for the definition
format, limits, and resume behavior.

When direct NTVMR access is unavailable, use the owner's local API proxy.
The current address is `http://192.168.0.119:8889`; this is the only concrete
local proxy address kept in tracked files. All other references use
`<local proxy>`. If the address changes, update this one reference.

Replace `https://ntvmr.uni-muenster.de` with `<local proxy>`, keeping the
endpoint path and query parameters. For the collector, declare
`"transport_base_url": "<local proxy>/community/vmr/api"` in the request
definition and pass the same base URL. Substitute the current address for
`<local proxy>` in the ignored `data/.cache/` definition and command before running:

```powershell
python collect_source_discovery.py --definition data/.cache/discovery-request.json --run-id declared-run --base-url "<local proxy>/community/vmr/api"
```

The proxy is an access route. Cite and link the canonical
`https://ntvmr.uni-muenster.de` sources; proxy URLs are not scholarly citations.
TLS verification and transport qualifications are not required for collection.
Permanent captures, discovery records, fixtures, and generated app data use
`<local proxy>` in transport URLs; the collector replaces the configured proxy
origin when saving them. Raw response bodies, hashes, retrieval dates, endpoint
paths, and parameters remain intact. Actual addresses belong only in local
commands and ignored `data/.cache/` definitions and request caches. Do not
hard-code them in scripts or copy them into other tracked files.

Keep the declared request budget, spacing, resume checkpoints, and provider-block
stops when using the proxy. A run's definition stays fixed; a transport change
uses a new run ID and carries prior attempts into the total budget.

Reuse each manuscript's metadata and contents locally, while discovering
candidates independently of previously selected witnesses. A report for one
verse does not prove that the candidate pool is sufficient for adjacent verses.
One usable scholarly report is enough; unresolved cases do not block collection.

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

```powershell
python build_collection.py --check
python build_na28_inventory.py --check
python -m unittest discover -s tests -v
npm test
```

Checks are offline. Do not start servers or make live source requests as routine
verification. The [development plan](docs/DEVELOPMENT_PLAN.md#next-development-work)
describes current priorities. Software revision history belongs in Git; the
working project maintains current data and a single app.
