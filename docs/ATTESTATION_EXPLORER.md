# Attestation explorer

The version 3 renderer produces a self-contained, offline single-page app. Open
[`examples/galatians-source-reports.html`](../examples/galatians-source-reports.html)
directly; no server, package installation, CDN, or live collection is needed.

One continuous horizontal chart contains all 7,957 coordinates in the existing
provisional GNT inventory, including supplementary traditional omitted verses.
The current example supplies reports for 149 Galatians coordinates only. The
remaining coordinates are marked **not collected**, or **filtered** when the
export's edition filters exclude them. Neither state implies manuscript absence
or a supported source-reference mapping. Only reference coordinates and editorial
statuses are taken from the full inventory; its historical mappings are not used.

## Interaction

- Hover a column to show its brief source summary below. Click or tap to hold
  that verse while following citations or opening source details. Release it to
  resume hover selection.
- The top-right optimistic/pessimistic control switches lower/upper reported
  endpoints in the same chart. Its year scale includes both scenarios and all
  exported alternatives and stays fixed when switching.
- Book navigation, exact reference entry (for example `Gal 1:9`), zoom, and
  horizontal scrolling make very thin columns accessible. The full overview can
  place several verses in one screen pixel; zoom or reference entry gives precise
  selection. Small-book labels are omitted when they cannot fit; every book is
  still available in the navigation menu.
- Focus the chart and use Left/Right for adjacent verses, Page Up/Down for 20
  verses, Home/End for the first/last coordinate, and Enter/Space to hold/release.
  Escape releases selection. Previous/next buttons provide the same precision
  on touch devices; dragging a zoomed chart pans horizontally.
- The source panel shows up to five witness summaries, with every witness and
  all exact claims, qualifications, retrieval dates, citations, complete date
  estimates, IDs, and hashes available in the expandable source details.
- Choose complete date alternatives under “About this view & date alternatives.”
  Initial choices follow assessment-ID order for illustration, without preference.
  Selections match exported per-verse combinations; no dates are recomputed or
  merged. Per-verse export overflow remains visible and unranked. The UI does not
  enumerate or impose a limit on the corpus-wide Cartesian product.

Unknown, contested, explicitly absent, filtered, and uncollected states remain
distinct in the source panel. Hatching marks collected columns with no dated
presence event; a terracotta strip marks verses with contested witness pairs,
even if other witnesses produce dated events. An explicitly absent pair never
supplies a presence event. Blank space below a first event means zero dated
witnesses at that year in the selected scenario, not manuscript absence.

## Reuse and extension

`render_attestation.render()` routes scholarly-report version 3 inputs through
[`report_explorer.py`](../report_explorer.py). Historical version 2 rendering is
unchanged. Collection, storage, export formats, and endpoint ranking remain in
their existing modules.

The adapter validates coordinate membership and duplicate IDs, interns repeated
claims and dates, and embeds a versioned display payload in an escaped
`application/json` element. It retains existing per-verse rankings rather than
re-ranking in JavaScript. `build_explorer_data(graph, inventory=None)` accepts an
explicit coordinate inventory for reuse; the default is the pinned provisional
GNT reference inventory. An empty report export is permitted; unknown or duplicate
coordinates fail explicitly.

The editable assets are in [`web/attestation-explorer/`](../web/attestation-explorer/):

| File | Responsibility |
| --- | --- |
| `index.html` | Accessible app shell and offline packaging placeholders |
| `explorer.css` | Responsive layout, colors, and typography |
| `explorer.js` | Pure display model plus DOM/canvas view |

The browser API is `AttestationExplorer.mount(root, data, {onSelect})`, returning
`setScenario("optimistic" | "pessimistic")`, `selectVerse("Gal 1:9")`, and
`destroy()` to disconnect listeners and resize observation. `onSelect` receives
the selected OSIS reference, scenario, and display state. Mount into a fresh copy
of the app shell. `createModel`, `hitIndex`, and `segments` are also exported for
offline Node tests. External source strings are rendered as text, and only
HTTP(S) citations become links.

Canvas draws the visible viewport with device-pixel scaling. Adjacent columns
with identical count steps share drawing operations to avoid subpixel fading;
hit testing still addresses individual coordinates. The DOM contains only the
current source summary, not thousands of verse elements. Resizing preserves the
center of a zoomed view. Style changes belong in CSS; additional dataset adapters
should produce the versioned display payload without changing the chart.

Regenerate after asset changes:

```powershell
python render_attestation.py --graph-input examples/galatians-source-reports-graph-input.json --output examples/galatians-source-reports.html
python render_attestation.py --graph-input examples/gal1-source-reports-graph-input.json --output examples/gal1-source-reports.html
python -m unittest discover -s tests -v
node --test tests/explorer.test.js
```

The Python suite tests full-corpus adaptation, retained provenance, safe HTML
embedding, and deterministic fresh replay. Node tests cover scenario changes,
date alternatives, overflow, coverage states, filters, book/reference navigation,
pointer coordinates, and simultaneous count steps. Browser layout/interaction
checks may open the generated local file directly; do not start a development
server or probe localhost for verification.
