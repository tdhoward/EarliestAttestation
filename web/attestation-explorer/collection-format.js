/* Versions 4–5 browser tables. See browser_format.py for the on-disk contract. */
(function (global) {
  "use strict";
  const object = value => value && typeof value === "object" && !Array.isArray(value);
  const fail = message => { throw new Error(message); };
  const integer = value => Number.isSafeInteger(value);
  const key = value => JSON.stringify(value);

  // Narrow only after reconstructing deltas: accumulating into an 8/16-bit
  // buffer would overflow even when its individual differences fit.
  function narrow(values) {
    if (Array.isArray(values)) return values;
    let min = 0, max = 0;
    for (const value of values) {min = Math.min(min, value); max = Math.max(max, value);}
    const Type = min >= 0 ? (max <= 255 ? Uint8Array : max <= 65535 ? Uint16Array : max <= 4294967295 ? Uint32Array : Float64Array) :
      min >= -2147483648 && max <= 2147483647 ? Int32Array : Float64Array;
    return values instanceof Type ? values : Type.from(values);
  }
  const column = (value, allowStrings = false) => narrow(decodeColumn(value, allowStrings));
  function decodeColumn(value, allowStrings = false) {
    if (Array.isArray(value)) {
      if (value.some(v => !integer(v) && !(allowStrings && typeof v === "string"))) fail("Invalid integer column");
      return allowStrings && value.some(v => typeof v === "string") ? value.slice() : Float64Array.from(value);
    }
    if (object(value) && Object.keys(value).length === 1 && Object.hasOwn(value, "deltas")) {
      if (object(value.deltas) && ((!Object.hasOwn(value.deltas, "runs") && !Object.hasOwn(value.deltas, "varints")) || Object.keys(value.deltas).length !== 1)) fail("Invalid nested delta column");
      const values = decodeColumn(value.deltas);
      let total = 0;
      for (let i = 0; i < values.length; i++) {
        total += values[i];
        if (!integer(total)) fail("Invalid delta column bounds");
        values[i] = total;
      }
      return values;
    }
    if (object(value) && Object.keys(value).length === 1 && Object.hasOwn(value, "varints")) {
      const spec = value.varints;
      if (!Array.isArray(spec) || spec.length !== 2 || !integer(spec[0]) || spec[0] < 0 || spec[0] > 50000000 ||
          typeof spec[1] !== "string") fail("Invalid varint column");
      const [length, text] = spec, alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
      const padding = text.indexOf("=");
      if (text.length % 4 || (padding >= 0 && !((padding % 4 === 2 && text.slice(padding) === "==") ||
          (padding % 4 === 3 && text.slice(padding) === "=")))) fail("Invalid varint base64");
      const values = new Float64Array(length);
      let bits = 0, buffer = 0, total = 0, multiplier = 1, offset = 0;
      for (const char of text) {
        if (char === "=") break;
        const code = alphabet.indexOf(char);
        if (code < 0) fail("Invalid varint base64");
        buffer = (buffer << 6) | code; bits += 6;
        if (bits < 8) continue;
        bits -= 8;
        const byte = (buffer >> bits) & 255;
        buffer &= (1 << bits) - 1;
        total += (byte & 127) * multiplier;
        if (total > 4294967295 || multiplier > 128 ** 4) fail("Invalid varint bounds");
        if (byte & 128) multiplier *= 128;
        else {
          if (offset >= length || (multiplier > 1 && byte === 0)) fail("Invalid varint length or value");
          values[offset++] = total % 2 === 0 ? total / 2 : -(total + 1) / 2;
          total = 0; multiplier = 1;
        }
      }
      if (buffer || multiplier !== 1 || offset !== length) fail("Mismatched varint column");
      return values;
    }
    if (!object(value) || Object.keys(value).length !== 1 || !Array.isArray(value.runs) || value.runs.length % 3) fail("Invalid integer runs");
    const runs = value.runs;
    let length = 0;
    for (let i = 0; i < runs.length; i += 3) {
      const [start, step, count] = runs.slice(i, i + 3);
      if (![start, step, count].every(integer) || count <= 0 || !integer(start + step * (count - 1))) fail("Invalid integer run bounds");
      length += count;
      if (length > 50000000) fail("Integer column exceeds supported size");
    }
    const values = new Float64Array(length);
    let offset = 0;
    for (let i = 0; i < runs.length; i += 3) {
      for (let n = 0; n < runs[i + 2]; n++) values[offset++] = runs[i] + runs[i + 1] * n;
    }
    return values;
  }

  function createStore(raw, {copyJSON: copy, freezeJSON: freeze}) {
    const arrayNames = ["coordinates", "providers", "claim_contexts", "claim_references", "coverage_contexts",
      "coverage_defaults", "observation_contexts", "discovery_records", "ranking_templates", "ranking_events", "documents", "sources"];
    if (!object(raw) || ![4, 5].includes(raw.format_version) || arrayNames.some(name => !Array.isArray(raw[name])) ||
        ["observations", "index_claims", "claims", "dates", "coverage_records"].some(name => !object(raw[name]))) fail("Invalid relational collection tables");
    const version = raw.format_version;
    if (version === 5 && (!object(raw.coordinate_statuses) || !object(raw.observation_defaults))) fail("Invalid format 5 defaults");
    const coordinates = version === 5 ? raw.coordinates.map((ref, i) => [ref, raw.coordinate_statuses[i] ?? "main"]) : raw.coordinates;
    if (version === 5) for (const [id, status] of Object.entries(raw.coordinate_statuses)) {
      if (!/^(0|[1-9][0-9]*)$/.test(id) || Number(id) >= coordinates.length || typeof status !== "string") fail("Invalid coordinate status");
    }
    const lookup = (values, id, label) => {
      if (!integer(id) || id < 0 || id >= values.length) fail(`Invalid ${label} reference`);
      return values[id];
    };
    const contexts = name => raw[name].map(value => {
      if (!object(value)) fail(`Invalid ${name} record`);
      return copy(value);
    });
    const provider = record => {
      const value = copy(record);
      if (Object.hasOwn(value, "provider_id")) {
        if (Object.hasOwn(value, "provider")) fail("Duplicate provider field");
        value.provider = lookup(raw.providers, value.provider_id, "provider"); delete value.provider_id;
      }
      return freeze(value);
    };
    const claimContexts = contexts("claim_contexts").map(provider);
    const coverageContexts = contexts("coverage_contexts").map(freeze);
    const observationContexts = contexts("observation_contexts").map(c => freeze(version === 5 ? {...copy(raw.observation_defaults), ...c} : c));
    const discovery = contexts("discovery_records").map(freeze);
    const dates = Object.fromEntries(Object.entries(raw.dates).map(([id, value]) => {
      if (!object(value)) fail("Invalid date record");
      return [id, provider(value)];
    }));
    const date = id => Object.hasOwn(dates, id) ? dates[id] : undefined;
    const dateReference = id => { if (!date(id)) fail("Dangling date reference"); };
    const refs = new Map();
    coordinates.forEach((value, id) => {
      if (!Array.isArray(value) || typeof value[0] !== "string" || refs.has(value[0])) fail("Invalid coordinate");
      refs.set(value[0], String(id));
    });
    const references = raw.claim_references.map(value => {
      if (!Array.isArray(value) || value.length !== 2) fail("Invalid claim reference");
      return [lookup(coordinates, value[0], "coordinate")[0], copy(value[1])];
    });
    const columns = Object.fromEntries(["ids", "contexts", "references", "pages", "locators"].map(name => [name, column(raw.index_claims[name])]));
    const size = columns.ids.length;
    if (Object.values(columns).some(c => c.length !== size)) fail("Mismatched claim columns");
    for (let i = 0; i < size; i++) {
      if (i && columns.ids[i] <= columns.ids[i - 1]) fail("Claim IDs must be unique and sorted");
      const context = lookup(claimContexts, columns.contexts[i], "claim context");
      lookup(references, columns.references[i], "claim reference");
      if (!integer(context.doc_id) || columns.locators[i] < 0) fail("Invalid compact index claim");
      if (["claim_id", "source_ref", "page_id", "reported", "source_locator"].some(field => Object.hasOwn(context, field))) fail("Packed claim overrides its context");
    }
    // Dense numeric IDs get a small typed index; sparse IDs use binary search.
    // Neither path constructs millions of dictionary entries or claim objects.
    const idBase = columns.ids[0], idSpan = size ? columns.ids[size - 1] - idBase + 1 : 0;
    const direct = idSpan > 0 && idSpan <= size * 2 ? new Int32Array(idSpan).fill(-1) : null;
    if (direct) for (let i = 0; i < size; i++) direct[columns.ids[i] - idBase] = i;
    function claimIndex(id) {
      const number = Number(id);
      if (!integer(number) || String(number) !== String(id)) return -1;
      if (direct) return number >= idBase && number < idBase + idSpan ? direct[number - idBase] : -1;
      let low = 0, high = size - 1;
      while (low <= high) {
        const mid = Math.floor((low + high) / 2), current = columns.ids[mid];
        if (current === number) return mid;
        if (current < number) low = mid + 1; else high = mid - 1;
      }
      return -1;
    }
    const literals = Object.create(null);
    for (const [id, packed] of Object.entries(raw.claims)) {
      if (!Array.isArray(packed) || packed.length !== 3 || claimIndex(id) >= 0) fail("Invalid literal claim");
      const [tag, index, details] = packed, context = lookup(claimContexts, index, "claim context");
      let fields = details;
      if (tag === "ntvmr_index_v1") {
        if (!Array.isArray(details) || details.length !== 4 || !integer(Number(id)) || String(Number(id)) !== id ||
            !integer(context.doc_id) || !integer(details[2]) || !integer(details[3]) || details[3] < 0) fail("Invalid compact index claim");
        const [content, osis, page, locator] = details;
        fields = {claim_id: Number(id), source_ref: osis, page_id: page,
          reported: {docID: context.doc_id, indexContent: content, osisID: osis, pageID: page},
          source_locator: `data.indexContents.indexContent[${locator}]`};
      } else if (tag !== "literal" || !object(details)) fail("Invalid literal claim");
      if (Object.keys(fields).some(field => Object.hasOwn(context, field))) fail("Packed claim overrides its context");
      literals[id] = freeze({...context, ...copy(fields)});
    }
    const literalIds = new Set(Object.values(literals).filter(c => Object.hasOwn(c, "claim_id")).map(c => key(c.claim_id)));
    const claimField = (id, field) => {
      if (Object.hasOwn(literals, id)) return literals[id][field];
      const index = claimIndex(id);
      return index < 0 ? undefined : field === "claim_id" ? columns.ids[index] : claimContexts[columns.contexts[index]][field];
    };
    const cache = new Map();
    function claim(id) {
      if (Object.hasOwn(literals, id)) return literals[id];
      const index = claimIndex(id);
      if (index < 0) return undefined;
      if (!cache.has(index)) {
        if (cache.size >= 4096) cache.delete(cache.keys().next().value);
        const context = claimContexts[columns.contexts[index]], [osis, content] = references[columns.references[index]];
        const page = columns.pages[index], locator = columns.locators[index];
        cache.set(index, freeze({...context, claim_id: columns.ids[index], source_ref: osis, page_id: page,
          reported: {docID: context.doc_id, indexContent: copy(content), osisID: osis, pageID: page},
          source_locator: `data.indexContents.indexContent[${locator}]`}));
      }
      return cache.get(index);
    }
    for (const context of coverageContexts) {
      if (Object.hasOwn(context, "claims") || !Array.isArray(context.date_assessments)) fail("Invalid coverage context");
      context.date_assessments.forEach(dateReference);
    }
    const contextual = version === 5 && object(raw.coverage_records.claims) && Object.hasOwn(raw.coverage_records.claims, "context_deltas");
    if (contextual && Object.keys(raw.coverage_records.claims).length !== 1) fail("Invalid contextual claim column");
    const coverage = Object.fromEntries(["contexts", "lengths"].map(name => [name, column(raw.coverage_records[name])]));
    // Decode predictions in Float64 before narrowing; claim IDs may exceed 32 bits.
    coverage.claims = contextual ? decodeColumn(raw.coverage_records.claims.context_deltas) : column(raw.coverage_records.claims, true);
    if (coverage.contexts.length !== coverage.lengths.length) fail("Mismatched coverage columns");
    const offsets = new Uint32Array(coverage.lengths.length + 1);
    for (let i = 0; i < coverage.lengths.length; i++) {
      lookup(coverageContexts, coverage.contexts[i], "coverage context");
      if (coverage.lengths[i] < 0) fail("Invalid coverage length");
      const next = offsets[i] + coverage.lengths[i];
      if (next > coverage.claims.length) fail("Mismatched coverage claim column");
      offsets[i + 1] = next;
    }
    if (offsets[offsets.length - 1] !== coverage.claims.length) fail("Mismatched coverage claim column");
    delete coverage.lengths; // Offsets replace lengths after validation.
    if (contextual) {
      const previous = new Float64Array(coverageContexts.length);
      for (let i = 0; i < coverage.contexts.length; i++) {
        const context = coverage.contexts[i];
        for (let j = offsets[i]; j < offsets[i + 1]; j++) {
          const value = previous[context] + coverage.claims[j];
          if (!integer(value)) fail("Invalid contextual delta bounds");
          previous[context] = value; coverage.claims[j] = value;
        }
      }
      coverage.claims = narrow(coverage.claims);
    }
    for (const id of coverage.claims) {
      if (claimIndex(id) >= 0) continue;
      if (!Object.hasOwn(literals, id)) fail("Dangling coverage claim reference");
      if (literals[id].assertion === "present" && literals[id].claim_id === undefined) fail("Missing coverage claim identifier");
    }
    const coverageReference = id => { lookup(coverage.contexts, id, "coverage"); };
    const coverageContext = id => coverageContexts[coverage.contexts[id]];
    const coverageClaims = id => Array.from(coverage.claims.slice(offsets[id], offsets[id + 1]), String);
    const defaults = raw.coverage_defaults.map(value => {
      const vector = column(value); for (const id of vector) coverageReference(id); return vector;
    });
    const rankings = contexts("ranking_templates");
    const rankingEvents = contexts("ranking_events").map(freeze);
    const rankingWitnesses = [];
    function* events(template) {
      if (!object(template) || !Array.isArray(template.combinations)) fail("Invalid ranking template");
      for (const combo of template.combinations) {
        if (!object(combo) || !object(combo.scenarios)) fail("Invalid ranking combination");
        for (const list of Object.values(combo.scenarios)) {
          if (!Array.isArray(list)) fail("Invalid ranking scenario");
          yield* list;
        }
      }
    }
    function validateEvent(event) {
      if (!object(event) || !Object.hasOwn(event, "witness_id") || !Number.isFinite(event.event_year)) fail("Invalid ranking event");
      dateReference(event.assessment_id);
      const tag = event.coverage_claim_ids;
      if (Array.isArray(tag) && tag.length === 1 && tag[0] === "pair") return;
      if (!Array.isArray(tag) || tag.length !== 2 || tag[0] !== "literal" || !Array.isArray(tag[1])) fail("Invalid event claim encoding");
      for (const id of tag[1]) if (!(typeof id === "number" && claimIndex(id) >= 0) && !literalIds.has(key(id))) fail("Dangling event claim reference");
    }
    rankingEvents.forEach(validateEvent);
    for (const template of rankings) {
      if (!Array.isArray(template.combinations)) fail("Invalid ranking template");
      for (const combo of template.combinations) {
        combo.assessments = Array.from(column(combo.assessments, true), String);
        combo.assessments.forEach(dateReference);
        if (!object(combo.scenarios)) fail("Invalid ranking combination");
        combo.scenarios = Object.fromEntries(Object.entries(combo.scenarios).map(([side, ids]) => {
          if (!Array.isArray(ids)) fail("Invalid ranking scenario");
          return [side, ids.map(id => lookup(rankingEvents, id, "ranking event"))];
        }));
      }
      const witnesses = new Set();
      for (const event of events(template)) {
        const tag = event.coverage_claim_ids;
        if (tag[0] === "pair") witnesses.add(key(event.witness_id));
      }
      rankingWitnesses.push(witnesses); freeze(template);
    }
    for (const context of observationContexts) {
      if (Object.hasOwn(context, "reported_coverage")) fail("Observation context contains coverage");
      lookup(rankings, context.dating_alternatives, "ranking"); lookup(discovery, context.discovery, "discovery");
    }
    const observations = new Map(), summaries = new Map();
    function* coverageKeys(row) {
      if (row[1] === 0) {yield* row[2]; return;}
      const vector = defaults[row[2]];
      let next = 0;
      for (let pos = 0; pos < vector.length; pos++) yield row[3][next] === pos ? row[4][next++] : vector[pos];
    }
    // Validate the complete reference graph once, and cache small totals. Drawing
    // must not rescan the 18M witness/verse matrix on every interaction.
    for (const [coordinate, packed] of Object.entries(raw.observations)) {
      if (!/^(0|[1-9][0-9]*)$/.test(coordinate)) fail("Invalid observation coordinate");
      const ref = lookup(coordinates, Number(coordinate), "coordinate")[0];
      if (!Array.isArray(packed)) fail("Invalid observation");
      const context = lookup(observationContexts, packed[0], "observation context");
      let row;
      if (packed[1] === 0 && packed.length === 3) {
        row = [packed[0], 0, column(packed[2])];
        for (const id of row[2]) coverageReference(id);
      } else if (packed[1] === 1 && packed.length === 5) {
        const vector = lookup(defaults, packed[2], "coverage default"), positions = column(packed[3]), records = column(packed[4]);
        if (positions.length !== records.length) fail("Mismatched override columns");
        for (let i = 0; i < positions.length; i++) {
          if (positions[i] < 0 || positions[i] >= vector.length || (i && positions[i] <= positions[i - 1])) fail("Invalid coverage override position");
          coverageReference(records[i]);
        }
        row = [packed[0], 1, packed[2], positions, records];
      } else fail("Invalid coverage encoding");
      observations.set(ref, row);
      const expected = rankingWitnesses[context.dating_alternatives], matches = new Map();
      const totals = {present: 0, unknown: 0, contested: 0, absent: 0};
      for (const id of coverageKeys(row)) {
        const pair = coverageContext(id), witness = key(pair.witness_id);
        totals[pair.state] = (totals[pair.state] || 0) + 1;
        if (expected.has(witness)) matches.set(witness, (matches.get(witness) || 0) + 1);
      }
      for (const witness of expected) if (matches.get(witness) !== 1) fail("Missing or ambiguous coverage pair reference");
      summaries.set(ref, freeze({editorial_status: context.editorial_status, ranking_state: context.ranking_state,
        discovery: discovery[context.discovery], contested: totals.contested > 0, coverage_totals: totals}));
    }
    const excluded = new Set([...arrayNames.filter(n => !["coordinates", "documents", "sources"].includes(n)),
      "observations", "index_claims", "claims", "dates", "coverage_records", "coordinate_statuses", "observation_defaults"]);
    const data = freeze(Object.fromEntries(Object.entries(raw).filter(([name]) => !excluded.has(name)).map(([name, value]) => [name, copy(name === "coordinates" ? coordinates : value)])));
    const chartViews = new Map(), chartEvents = new Map();
    function chartEvent(event) {
      if (!chartEvents.has(event)) {
        const {coverage_claim_ids, ...display} = event;
        chartEvents.set(event, freeze(display));
      }
      return chartEvents.get(event);
    }
    const alternativeIndex = ref => observationContexts[observations.get(ref)[0]].dating_alternatives;
    function chartView(index) {
      if (!chartViews.has(index)) chartViews.set(index, freeze({...rankings[index], combinations: rankings[index].combinations.map(combo => ({...combo,
        scenarios: Object.fromEntries(Object.entries(combo.scenarios).map(([side, list]) => [side, list.map(chartEvent)]))}))}));
      return chartViews.get(index);
    }
    let cachedRef, cachedObservation, observationDecodes = 0, coverageDecodes = 0;
    function observation(ref) {
      if (cachedRef === ref) return cachedObservation;
      cachedRef = ref; cachedObservation = null;
      const row = observations.get(ref);
      if (!row) return null;
      observationDecodes++;
      const context = observationContexts[row[0]], byWitness = new Map();
      const pairs = Array.from(coverageKeys(row), id => {
        coverageDecodes++;
        const pair = {...copy(coverageContext(id)), claims: coverageClaims(id)};
        byWitness.set(key(pair.witness_id), pair); return pair;
      });
      const ranking = copy(rankings[context.dating_alternatives]);
      for (const event of events(ranking)) {
        const tag = event.coverage_claim_ids;
        event.coverage_claim_ids = tag[0] === "literal" ? tag[1] : byWitness.get(key(event.witness_id)).claims
          .filter(id => claimField(id, "assertion") === "present").map(id => claimField(id, "claim_id"));
      }
      cachedObservation = freeze({...copy(context), reported_coverage: pairs, dating_alternatives: ranking, discovery: copy(discovery[context.discovery])});
      return cachedObservation;
    }
    const typedArrayBytes = Object.values(columns).reduce((n, v) => n + v.byteLength, 0) + (direct?.byteLength || 0) +
      coverage.contexts.byteLength + (coverage.claims.byteLength || 0) + offsets.byteLength +
      defaults.reduce((n, v) => n + v.byteLength, 0) + Array.from(observations.values()).reduce((n, r) =>
        n + (r[1] === 0 ? r[2].byteLength : r[3].byteLength + r[4].byteLength), 0);
    raw = null; // The store owns copied small records and numeric columns, not the parsed transfer tree.
    return Object.freeze({data, formatVersion: version, dateIds: Object.freeze(Object.keys(dates)), date, claim, observation,
      hasObservation: ref => observations.has(ref), summary: ref => summaries.get(ref) || null,
      chartAlternatives: ref => observations.has(ref) ? chartView(alternativeIndex(ref)) : null,
      *chartRecords() {for (const index of new Set(Array.from(observations.keys(), alternativeIndex))) yield chartView(index);},
      diagnostics: () => Object.freeze({observationDecodes, coverageDecodes, chartTemplates: chartViews.size,
        cachedObservations: cachedObservation ? 1 : 0, cachedClaims: cache.size, typedArrayBytes, chartEvents: chartEvents.size}),
      // Explicit compatibility/export API only. Never called by chart loading.
      expandData() {
        const claims = {...literals};
        for (const id of columns.ids) claims[String(id)] = claim(id);
        return copy({...data, format_version: 1, claims, dates,
          observations: Object.fromEntries(Array.from(observations.keys(), ref => [ref, observation(ref)]))});
      }});
  }
  const api = {createStore, column};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else global.AttestationFormat = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
