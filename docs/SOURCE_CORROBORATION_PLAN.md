# Source corroboration plan

Agreed direction: 2026-10-08. Status: planned; the checking register, additional
source collectors, and discrepancy workflow below are not yet implemented.
This is the shared working plan, updated in place as work proceeds. Follow
[AGENTS.md](../AGENTS.md) and the [development plan](DEVELOPMENT_PLAN.md).

## Purpose and present limitation

Improve the accuracy of reported manuscript contents and dates by adding usable
scholarly sources, recording exactly what has been checked, and exposing
disagreements in the existing explorer. One usable scholarly report remains
sufficient. Corroboration is not a prerequisite for every witness or a claim that
we have independently established a manuscript's physical contents.

The Pericope Adulterae investigation found that the saved NTVMR index includes all
twelve verses of John 7:53–8:11 for P66, P75, and Vaticanus. The current importer
converts those entries into ordinary presence claims. Relevant saved page ranges:

| Witness | NTVMR page ID | Indexed range in captured metadata |
| --- | --- | --- |
| [P66](../data/sources/ntvmr-10066-metadata-591ac6c6de89106b.json) | 480 | John 7:52–53; John 8:1–16 |
| [P75](../data/sources/ntvmr-10075-metadata-f23780f58cf31e65.json) | 840 | John 7:49–53; John 8:1–22 |
| [Vaticanus](../data/sources/ntvmr-20003-metadata-93125714bc733b74.json) | 1300 | John 7:32–53; John 8:1–19 |

The [retained endpoint documentation](../data/reference/contracts/biblicalcontent_get_.json)
describes `detail=long` as expanding page ranges into individual entries.
[Daniel Wallace's published discussion](https://www.biblicaltraining.org/learn/institute/nt605-textual-criticism/nt605-33-some-famous-textual-problems-john-7-53-8-11)
explicitly reports omission in P66, P75, Sinaiticus, and Vaticanus.
[H. A. G. Houghton's discussion, section 2.F](https://pure-oai.bham.ac.uk/ws/portalfiles/portal/29525014/Houghton_OHJS_preprint.pdf)
provides further scholarly context and identifies Bezae as the earliest surviving
Greek witness containing the passage. These publications are leads for capture
and faithful extraction; links in this plan do not register production claims.

We have not established whether NTVMR intends its page ranges to account for
internal textual omissions. These could be incorrect index entries, a limitation
of the indexing convention, or both. Do not describe either explanation as
confirmed. The three forum links supplied during discussion could not be retrieved
and have not established a provider explanation or correction:
[2319157](https://ntvmr.uni-muenster.de/forum/-/message_boards/message/2319157),
[2378155](https://ntvmr.uni-muenster.de/forum/-/message_boards/message/2378155),
[2378979](https://ntvmr.uni-muenster.de/forum/-/message_boards/message/2378979).

## Evidence rules

- Use explicit scholarly catalogue fields and published assertions with documented
  meanings. An API is optional: organized web pages, XML, JSON, tables, and
  downloadable publications are acceptable sources.
- Capture source material and extract its assertions. Never determine contents,
  dates, identity, damage, hands, or corrections from manuscript images, Greek
  transcription text, an apparatus, or empty transcription elements.
- Record the source's exact scope. A report about one passage does not validate
  the rest of a manuscript. A broad book/chapter range does not establish every
  intervening verse unless the source's documented meaning supports that use.
- Any reported surviving portion counts once. Missing entries and incomplete
  source coverage establish neither absence nor disagreement.
- Distinguish actual incompatible content assertions from ambiguous indexing or
  extraction/mapping problems. Agent interpretations never become scholarly claims.
- Preserve complete competing date intervals and qualifications with equal
  standing. Overlap does not make two estimates identical; difference does not
  establish that one is erroneous. Never average, intersect, or merge endpoints.
- Retain source attribution and known upstream dependencies. Two sites repeating
  the same catalogue are two access points, not necessarily independent evidence.

## Storage and checking register

Keep one central collection and one app. The proposed additional register is
`data/source_checks.json`, covering content and date comparisons. Do not create
book-specific datasets, milestone reports, or a second manuscript truth store.

| Location | Planned responsibility |
| --- | --- |
| `data/sources/` | Captured source responses/pages or publications and their retrieval metadata |
| `data/reference/` | Captured field documentation and source contracts where needed |
| `data/collection.json` | Canonical witness identities and registered scholarly claims, using or extending `additional_reports` |
| `data/source_checks.json` | Work queue, exact comparison scope, evidence references, outcomes, and follow-up state |
| `data/attestations.json` | Derived app evidence, coverage consequences, and compact discrepancy/check summaries |
| `data/.cache/` | Ignored request checkpoints, experiments, and temporary build databases |

Finalize a versioned register schema during implementation. Each check should
record a stable ID; canonical witness/document IDs; content or date comparison
kind; exact verse scope or date applicability; NTVMR and comparison-source capture
IDs/hashes; source locators and claim IDs; comparison method/version; checked date;
outcome and explanation; and follow-up status with supporting evidence.

Each capture retains provider/author, title and citation, canonical URL, retrieval
timestamp, raw material and hash where available, exact field or statement,
qualifications, and any known upstream source. Large captures are referenced, not
duplicated into every check. Extraction locators must make the assertion easy to
find in the saved source. Handle aliases/joins only through cited identity reports.

Keep comparison outcomes separate from manuscript coverage:

| Check outcome | Meaning |
| --- | --- |
| Not yet checked | No completed comparison for this witness, scope, and source |
| Agreement | Comparable explicit content assertions agree within the recorded scope, or complete date estimates agree |
| Disagreement | Comparable explicit content assertions conflict, or complete date estimates differ; identify which kind |
| Insufficient detail | A comparison was attempted, but ambiguity, missing assertions, unsupported mapping, or insufficient scope prevents a conclusion |

Track access failures separately from evidence outcomes. Distinguish open,
deferred, and resolved follow-up from the comparison result. A resolution needs
an attributable correction, clarification, or repaired extraction; it must not
erase the original captures or disagreement. A newer source snapshot or changed
extraction rule marks affected checks as needing recheck. Earlier agreement must
not silently apply to new evidence. Software revision history remains in Git.

Do not use an unqualified manuscript-wide "validated" checkbox. Summaries should
say, for example, "John 7:53–8:11 checked against source X," and distinguish full
declared-scope checks from partial ones. Date checking does not imply content
checking. Discovery completion does not imply either.

## App behavior

Full checking records stay outside `attestations.json`. The normal offline build
should project only the details needed by the app into that file, preserving its
single-file loading path. Registered scholarly assertions determine coverage;
checking records reference those assertions rather than supplying uncited overrides.

For each affected verse, show the manuscript, the NTVMR claim/index entry, the
other source's statement, exact scope, citations/capture links, and follow-up state.
Also provide a way to find open discrepancies and inspect checking progress.

- Incompatible explicit presence/absence reports are `contested`, visible, and
  excluded from ordinary presence counts and rankings while unresolved.
- An ambiguous NTVMR index remains visible as an interpretation issue, without
  being promoted to an opposing scholarly assertion. Its unsupported contribution
  is `unknown`; an independently usable report may still establish presence or
  explicit absence. Explain the issue in the app even when it is not `contested`.
- Different complete date estimates remain visible alternatives under the existing
  date-scenario behavior, not a content conflict or an averaged replacement date.
- Missing comparison data leaves the checking status incomplete; it does not
  negate an otherwise usable scholarly report. Continue unrelated collection.

A discrepancy notice must agree with coverage and rankings. Do not display an
unresolved conflict only as a footnote while counting that pair as ordinary
presence. No application change described here has yet corrected the current data.

## Candidate sources and evaluation

This shortlist records the initial investigation, not a ranking of source
accuracy. Verify field meanings, availability, reuse conditions, and provenance
before building a collector. A downloadable dataset can be as useful as an API.

| Candidate | Initial assessment and next check |
| --- | --- |
| [CSNTM](https://www.csntm.org/2026/02/16/how-to-read-and-understand-a-manuscript-record-in-the-csntm-database/) | Prioritize evaluation of explicit contents descriptions and reported dates. No documented public metadata API was located. Determine whether available descriptions distinguish omissions and whether they reuse NTVMR or another catalogue. |
| [Papyri.info / DCLP / APIS](https://github.com/papyri/idp.data) | Public XML data makes a bounded metadata pilot practical. Establish relevant manuscript coverage and usable explicit assertions; do not analyze transcription bodies. [DCLP documentation](https://github.com/papyri/site-docs/blob/master/dclp.md) identifies LDAB as its initial metadata source. |
| [Trismegistos / LDAB](https://www.trismegistos.org/dataservices/texrelations/documentation/) | The documented matcher links identifiers across projects. Use it for source discovery and identity cross-references; it does not itself provide verse-presence assertions. |
| [IRHT / Arca](https://www.irht.cnrs.fr/fr/ressources/autre/arca-api) and [Biblissima](https://doc.biblissima.fr/api/api-mediawiki/) | Potential catalogue enrichment and identity links through documented APIs. No comprehensive NT verse-content service has been established. |
| [IGNTP / ITSEE](https://itseeweb.cal.bham.ac.uk/iohannes/download.html) and [CNTR](https://github.com/Center-for-New-Testament-Restoration/transcriptions) | Available transcription/apparatus downloads are not direct coverage inputs under our scope. Use separately published explicit scholarly reports if available. |
| Published catalogues and scholarly discussions | Capture explicit statements for known discrepancies, including the Pericope Adulterae. Retain page/section locators; neither automated prose extraction nor source reputation alone establishes a claim's scope. |

No resource has yet been demonstrated to quickly vet the verse contents of most
relevant witnesses. Evaluate that possibility through a pilot rather than treating
broad catalogue overlap or downloadable transcriptions as completed validation.

## Ordered work and shared checkpoints

All steps below are pending. Update these checkboxes and current findings in place.

1. [ ] **Clarify the NTVMR contract and record the known case.** Reuse retained
   metadata, contents, and help captures. Seek documentation or a published provider
   clarification about internal omissions; do not assume a forum report proves a
   correction. Capture the explicit scholarly reports for John 7:53–8:11. Include
   P66, P75, Vaticanus, Sinaiticus, and Bezae with their actual report states; a
   missing index entry alone is not an absence assertion. Record unresolved field
   meaning without blocking the remaining work. Checkpoint: review the evidence
   and the proposed classification before changing the general import contract.
2. [ ] **Implement the register and evidence links.** Define its schema and scope
   rules, connect checks to canonical witnesses/captures/claims, and support
   resumable work and rechecking. Preserve complete date alternatives. Checkpoint:
   review a small set of records that makes clear what was and was not checked.
3. [ ] **Connect discrepancies to the existing app.** Update the source contract,
   normalization, export, and explorer together. Add visible discrepancy details
   and progress summaries, with correct coverage/count consequences. Checkpoint:
   review the Pericope Adulterae example and both date modes in the resulting app;
   the owner starts the local server when needed.
4. [ ] **Run a bounded source pilot.** Start with CSNTM and Papyri.info metadata plus
   explicit publications. Declare witness IDs, passages, sources, time/request
   budgets, and pacing before live work. Include ordinary contents, fragmentary
   reports, published omissions, and competing date estimates; sample the relevant
   catalogue categories without treating the sample as comprehensive. Measure
   usable exact claims, scoped agreements/disagreements, unresolved cases, requests,
   extraction effort, and known shared upstream sources. Checkpoint: decide which
   sources and extraction contracts merit broader collection.
5. [ ] **Expand useful sources and maintain checks.** Work through the relevant
   central witness pool using the durable queue. Reuse captures, respect provider
   limits/blocks, and keep each live run finite. Report full versus partial checking
   coverage and outstanding discrepancies. Recheck affected scopes after source
   updates. Preserve the existing date scope unless explicitly changed; do not
   expand it merely to fill ranking places.

At checkpoints, human review checks extraction, citations, usability, and source
priorities; it does not require manuscript examination or scholarly certification.
Routine reversible work can continue within the agreed scope. Contacting providers
or posting reports requires the owner's explicit instruction; research and record
preparation do not authorize sending messages.

## Acceptance and verification

- Every check identifies the exact witness, scope, sources, snapshots, and outcome;
  progress cannot mistake a partial check for whole-manuscript validation.
- Original evidence survives extraction fixes, source updates, and resolutions;
  later snapshots do not inherit stale agreement silently.
- The known Pericope Adulterae cases no longer contribute unsupported ordinary
  presence. The displayed result follows explicit reports and the documented
  contract, without inferred absence or manufactured scholarly disagreement.
- Actual content conflicts affect counts/rankings; ambiguous fields and missing
  comparisons stay distinct. Other witnesses remain usable. Any reported portion
  counts once; aliases, repeated pages, and repeated sources do not multiply it.
- Competing dates retain their full intervals, original notation, qualifications,
  and source attribution. Contents checks do not certify dates or vice versa.
- Bounded offline fixtures verify extraction, mapping, provenance, disagreement
  classification, deduplication, rechecking, date alternatives, and app output.
  No test asks us to determine what a manuscript physically contains.
- Use appropriate existing offline Python/Node checks and collection validation
  when implementation changes warrant them. No local server or live collection
  is part of routine verification. Keep one central collection, one current app
  data file, and one explorer.
