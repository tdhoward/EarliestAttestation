# EarliestAttestation

Collect and graph **what scholarly sources report** about the estimated ages
and verse contents of surviving Greek New Testament manuscripts. For each verse
of **NA28**, show up to five distinct witnesses using both ends of the reported
date ranges. The chart follows traditional book/chapter/verse order, places
newer years at the top, and changes color as the witness count increases.

## Project boundary

This is a data collection and visualization project. Neither the project owner
nor AI agents are undertaking manuscript scholarship. **Never download or inspect
manuscript images, read Greek transcriptions to determine surviving words, or
independently identify contents, hands, corrections, damage, or dates.** A source's
image or transcription link does not authorize examination.

Prefer explicit catalogue metadata and verse-content reports from NTVMR, using
its documented API semantics. Other scholarly catalogues and publications may
supply explicit claims where needed. One usable scholarly report is sufficient;
independent corroboration of every witness is not required. Preserve the source,
reported fields or statement, citation, retrieval date, and qualifications.
Do not turn missing information into a manuscript research task.

If a scholarly source reports that **any portion of a verse is present, count
that verse as present** for that witness. No complete verse, minimum number of
letters, exact NA28 wording, or independent survival check is required. This
counting rule does not extend a source's report to neighboring verses.

If scholarly sources explicitly disagree about a witness's verse contents, mark
that witness/verse **contested**, retain both reports, and defer the case while
continuing collection. Missing or ambiguous reports are **unknown**. A missing
index entry alone is neither absence nor disagreement; absence requires an
explicit scholarly report. Broad ranges are interpreted only according to the
source's documented meaning, without filling gaps independently.

These rules were clarified on **2026-10-05**. They are enforced as agent
instructions in [AGENTS.md](AGENTS.md) and supersede examination requirements in
older notes. The code still needs the adaptations described below.

## Witness scope

The corpus covers surviving Greek manuscript copies of the New Testament texts
themselves, including eligible fragments and lectionaries. Classification,
identity, and fragment joins come from scholarly sources. Multiple catalogue IDs,
pages, or holdings of the same reported physical witness must not inflate counts.

Quotations, paraphrases, and allusions in other works are outside the corpus,
including verbatim patristic quotations. A manuscript of Justin Martyr's work is
not an eligible copy of the quoted New Testament text. Printed editions,
catalogues, and scholarly publications are references, not additional witnesses.
Other witness categories require an explicit scope change.

## Development direction

The next milestone is a **reproducible NTVMR collection-to-chart pipeline using
reported dates and verse contents**, with unknown and contested cases visible.
The [development plan](docs/DEVELOPMENT_PLAN.md#next-development-work) is the
source of current priorities and acceptance criteria:

1. Document which NTVMR fields explicitly report dates, contents, identity, and
   discovery scope; use existing captures before any bounded live contract check.
2. Adapt the existing data path to accept those scholarly reports without our
   own image checks, word anchors, or writing-layer judgments. Preserve provenance
   and implement explicit disagreement as `contested`.
3. Re-source or exclude agent-derived claims from earlier examples, preserving
   their history. Rebuild one small chart entirely from attributable reports.
4. Expand document batches and reference mappings, fetching each manuscript's
   metadata and contents once where possible and ranking locally.

Measure progress by manuscripts collected, reported witness/verse pairs,
graphable coordinates, unresolved records, and collection efficiency. An
unresolved manuscript or disagreement does not block the rest of the dataset.
Manual examination, specialist certification, and general review-platform work
are outside the milestone. Human checks, when useful, verify faithful copying
and citation of published claims only.

## Manuscript dating policy

Preserve each source's estimated date range, original notation, qualifications,
and applicability. Use explicit numeric API bounds when supplied. Any conversion
of a complete century label to years must be documented; qualitative wording
without defensible bounds stays numerically unknown. Do not infer precision.

Defer to documented scholarly consensus where a cited source establishes it.
Otherwise retain sourced ranges as equally valid alternatives: do not choose a
preferred scholar, average or narrow ranges, merge endpoints, or assign
probabilities. Unknown consensus does not make an otherwise usable date unusable
and is not a reason to launch a dating investigation.

Record a different date for a portion, supplement, or hand only when a scholarly
source explicitly identifies that distinction and its applicability. Do not
create a requirement to examine or independently classify writing layers.
Ambiguous applicability remains unresolved. P52 is an existing example, not a
standing manuscript-research assignment.

## Skipped verses and graph inclusion

Retain traditional verse numbers skipped by NA28 as supplementary coordinates
tagged `omitted`. The default graph excludes them, with an **Include verses
omitted from NA28** option; bracketed passages have a separate inclusion control.
Edition status does not determine a manuscript's reported contents or age.

Apply the same scholarly-report and counting rules to core and supplementary
coordinates. Identify traditional passages from published references and map
source coordinates through documented versification rules. Keep unclear mappings
unresolved. Do not use Greek manuscript examination to settle a mapping.

Graphs, exports, and summary counts must identify active filters and their verse
population. Filtering preserves underlying reports. Unknown, contested, explicitly
reported absent, and filtered-out coordinates are distinct. Supplementary
collection must not block the core pipeline. See the
[inventory documentation](docs/NA28_INVENTORY.md).

## Current status

This is a Python/SQLite prototype. The existing collector supports scoped,
budgeted requests, immutable response capture, caching, and offline replay.
Schema version **12** also contains review and writing-unit interfaces from the
previous approach. The offline exporter and static renderer already implement
both endpoint scenarios and conditional date alternatives.

The provisional whole-NT inventory contains 7,957 coordinates across 27 books and
260 chapters, including 16 skipped traditional numbers. It is not a completed
manuscript collection or a complete source-to-NA28 mapping.

**The scope reset is documentation only.** A direct scholarly-report-to-chart
path and a `contested` coverage state are planned, not implemented by this
change. Existing conflict flags are not yet a representation of disagreements
between scholarly sources. Old storage and ranking gates still require adaptation.

Earlier John/Galatians charts, review manifests, and tests include agent judgments
from images or transcriptions. They remain historical prototypes pending an
attribution audit; their replay success does not establish compliance with the
current scope. The unfinished John 5 overlap drafts likewise are not approved
inputs. Do not continue their examination work or present their conclusions as
scholarly reports. Existing code, fixtures, databases, and charts are unchanged.

The [historical implementation and replay guide](docs/HISTORICAL_REPLAY_GUIDE.md)
preserves prior commands and observations. The
[historical development plan](docs/HISTORICAL_DEVELOPMENT_PLAN.md) preserves the
old milestones. Both are superseded, not task lists. The latest previously
recorded full run was 121 offline tests; that observation is not a new test run
or an endorsement of the old evidence policy.

## Controlled collection

[`sync_ntvmr.py`](sync_ntvmr.py) and [`controlled_ntvmr.py`](controlled_ntvmr.py)
use the standard library. The official HTTPS API is the default. Live work
requires an explicit scope and positive request budget. Attempts, including
retries and previous attempts under the same run ID, count toward that budget.
The minimum five-second interval is a project default, not a confirmed provider
quota. Establish provider expectations before bulk access, honor blocked states,
and keep TLS verification enabled.

Prefer existing captures and document batches over repeated requests per verse.
Keep search results distinct from explicit contents reports until the endpoint
contract establishes what each field means. Failed or incomplete collection is
not a report of empty contents. Do not claim exhaustive discovery from a bounded
list of chosen manuscripts.

```powershell
python sync_ntvmr.py --help
python sync_ntvmr.py --offline --fixture-p52 --db data/source-report-fixture.sqlite --run-id fixture-p52 --export-p52 examples/p52-index-sample.json
python sync_ntvmr.py --offline --db data/source-report-fixture.sqlite --doc-id 10052 --run-id contract-review --dry-run
```

These existing commands demonstrate collection and index extraction; they do not
implement the planned report-to-chart workflow. Always pass `--db` explicitly.
`--offline` prevents network requests but permits writes. Collector `--dry-run`
and report commands can create or upgrade the schema; they are not read-only.
Use fresh destinations or SQLite backup before modifying existing databases.

[`legacy_sync_ntvmr.py`](legacy_sync_ntvmr.py) is preserved with direct execution
disabled. Its exploratory `ntvmr.sqlite` must not be used as an authoritative
ranking dataset. The [original data review](docs/DATA_REVIEW.md) remains a
historical account of collection defects, not current examination instructions.

## Run the offline checks

Python 3.10+ is required. The collector, audits, and tests use the standard
library. The test suite uses temporary databases and makes no network requests.

```powershell
python -m unittest discover -s tests -v
python build_na28_inventory.py --review benchmarks/na28-coordinate-review-v2.json --passage-review benchmarks/na28-passage-identifications-v1.json --check
```

Run relevant tests when changing code. The new workflow's checks must establish
faithful extraction, source provenance, reference mapping, deduplication, coverage
states, date alternatives, rankings, and display. Retained historical tests do
not authorize image or transcription examination. No local development server or
localhost probe is needed or permitted unless requested by the owner.

The audit scripts open existing databases read-only; collection report commands
may upgrade them. Audits check structure and stored expectations. They do not
certify a manuscript's age or contents. Historical replay and audit commands are
available in the [archived guide](docs/HISTORICAL_REPLAY_GUIDE.md).

## Date scenarios and chart semantics

For each verse and identified date alternative, rank all eligible reported
witnesses twice: lower endpoints for the optimistic view, upper endpoints for
the pessimistic view. Select up to five separately in each view; their order
and membership may differ. Retain the complete intervals and their citations.
A physical witness counts once per verse regardless of pages, portions, or date
assessments. Any reported portion supplies one full verse-presence count.

For the planned workflow, contested coverage stays visible separately and does
not enter the ordinary presence count while deferred. Unknown dates do not
produce invented event years. Exports must distinguish this from absence or a
coordinate excluded by an edition filter.

Place newer years above older ones and use the same scale for both scenarios.
Counts rise from zero through five as events occur, with simultaneous events
handled together. Label the result as the earliest witnesses **reported in the
collected sources and declared scope**; neither scenario dates composition or
claims exhaustive discovery.

The existing version 2 exporter retains full and filtered outputs and enumerates
at most 256 conditional date combinations per verse. Overflow is explicit
(`too_many_combinations`), not silently truncated. On-demand exploration and a
structured consensus representation remain future work. Existing outputs still
use the older review inputs pending the pipeline adaptation.

## Files

| Path | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Binding scope boundary and working instructions |
| [Development plan](docs/DEVELOPMENT_PLAN.md) | Current priorities, data semantics, and acceptance criteria |
| [Inventory notes](docs/NA28_INVENTORY.md) | Publisher coordinates and pending source mappings |
| `sync_ntvmr.py`, `controlled_ntvmr.py` | Controlled collection and current v12 storage |
| `export_attestation.py`, `render_attestation.py` | Existing offline export and chart pipeline to adapt |
| `audit_ntvmr.py`, `audit_reviewed.py`, `tests/` | Structural and software checks, including historical fixtures |
| `replay_*.py`, `review_absence.py`, `benchmarks/`, `examples/` | Existing review interfaces and historical prototypes; require attribution audit before reuse as active results |
| [Historical replay guide](docs/HISTORICAL_REPLAY_GUIDE.md) | Superseded implementation notes and reproducibility commands |
| [Historical development plan](docs/HISTORICAL_DEVELOPMENT_PLAN.md) | Preserved milestones and withdrawn examination requirements |

Project code is licensed under [GPL-3.0](LICENSE). Source materials have their
own reuse terms; the code license does not grant redistribution rights to them.
