/* Reusable explorer view. Data loading lives in app.js. */
(function (global) {
  "use strict";
  const BOOKS = [
    ["Matt", "Matthew", "Mt"], ["Mark", "Mark", "Mk"], ["Luke", "Luke", "Lk"],
    ["John", "John", "Jn"], ["Acts", "Acts", "Ac"], ["Rom", "Romans", "Ro"],
    ["1Cor", "1 Corinthians", "1Co"], ["2Cor", "2 Corinthians", "2Co"],
    ["Gal", "Galatians", "Ga"], ["Eph", "Ephesians", "Ep"], ["Phil", "Philippians", "Php"],
    ["Col", "Colossians", "Col"], ["1Thess", "1 Thessalonians", "1Th"],
    ["2Thess", "2 Thessalonians", "2Th"], ["1Tim", "1 Timothy", "1Ti"],
    ["2Tim", "2 Timothy", "2Ti"], ["Titus", "Titus", "Ti"], ["Phlm", "Philemon", "Phm"],
    ["Heb", "Hebrews", "He"], ["Jas", "James", "Ja"], ["1Pet", "1 Peter", "1Pe"],
    ["2Pet", "2 Peter", "2Pe"], ["1John", "1 John", "1Jn"], ["2John", "2 John", "2Jn"],
    ["3John", "3 John", "3Jn"], ["Jude", "Jude", "Ju"], ["Rev", "Revelation", "Re"]
  ];
  const COLORS = ["#d1e4dd", "#a4cbbc", "#70ad96", "#39836e", "#185c4d"];
  const clamp = (n, low, high) => Math.max(low, Math.min(n, high));
  const normalize = value => value.toLowerCase().replace(/[\s.]/g, "");
  const interval = date => date.status === "valid" ? `${date.date_min}–${date.date_max} CE` : `${date.status} numeric bounds; unrankable`;

  const isRecord = value => value && typeof value === "object" && !Array.isArray(value);
  const copyJSON = value => Array.isArray(value) ? value.map(copyJSON) : isRecord(value) ?
    Object.fromEntries(Object.entries(value).map(([key, item]) => [key, copyJSON(item)])) : value;
  const readonlyRecords = new WeakSet();
  function freezeJSON(value) {
    if (value && typeof value === "object" && !readonlyRecords.has(value)) {
      readonlyRecords.add(value);
      for (const item of Object.values(value)) freezeJSON(item);
      Object.freeze(value);
    }
    return value;
  }
  const orderedJSON = value => Array.isArray(value) ? value.map(orderedJSON) : isRecord(value) ?
    Object.fromEntries(Object.keys(value).sort().map(key => [key, orderedJSON(value[key])])) : value;
  const jsonKey = value => JSON.stringify(orderedJSON(value));
  const stores = new WeakSet(), models = new WeakSet();

  // Browser format 3 mirrors the storage contract in report_explorer.py:
  // claims[id] = ["literal", contextIndex, details] or ["ntvmr_index_v1",
  //   contextIndex, [indexContent, osisID, pageID, locatorIndex]].
  // coverage_records[i] = [coverageContextIndex, orderedStringClaimIds].
  // observations[ref] = [observationContextIndex, coverageEncoding], where
  // coverageEncoding is ["dense", recordIndices] or
  // ["sparse", defaultsIndex, increasing [position, recordIndex] overrides].
  // Observation contexts refer to discovery_records and ranking_templates;
  // event claim IDs are ["pair"] (the unique witness pair's ordered present
  // claim IDs) or ["literal", originalIds]. Indices are zero-based. Shared
  // defaults create no observations or assertions; absent rows stay absent.
  // Preserve provenance, complete date alternatives, array order, JSON types,
  // and null/missing/extra fields. Versions 1/2 and private candidate markers
  // have compatibility paths; numeric 3 is the production browser schema.
  // expandData() provides independent mutable copies for explicit consumers.
  // The runtime takes ownership of the parsed JSON and freezes it. Validation
  // follows references in place, including unused tables; it never expands the
  // witness/verse matrix. Only observation() materializes a normalized row,
  // caching at most one verse. Claims cache by unique ID; chart events omit
  // claim lists and remain shared/read-only. Date selection lives in the model.
  function createDataStore(raw) {
    if (stores.has(raw)) return raw;
    if (raw?.format_version === 4) {
      const codec = typeof module !== "undefined" && module.exports ? require("./collection-format.js") : global.AttestationFormat;
      const store = codec.createStore(raw, {copyJSON, freezeJSON});
      stores.add(store);
      return store;
    }
    if (!isRecord(raw) || !Array.isArray(raw.coordinates) || !isRecord(raw.observations)) {
      throw new Error("Unsupported collection data");
    }
    const version = raw.format_version, normalized = version === 1;
    const sparse = version === 3 || version === "3-phase3";
    const compact = sparse || version === "3-phase2";
    const shared = compact || version === "3-phase1";
    if (!normalized && version !== 2 && !shared) throw new Error("Unsupported collection data");
    const tables = normalized ? [] : ["claim_contexts", "coverage_records", "discovery_records"];
    if (shared) tables.push("ranking_templates", "observation_contexts");
    if (compact) tables.push("coverage_contexts");
    if (sparse) tables.push("coverage_defaults");
    if (tables.some(name => !Array.isArray(raw[name])) || (!normalized && !isRecord(raw.claims))) {
      throw new Error("Missing collection record tables");
    }
    const claims = raw.claims || {}, dates = raw.dates || {};
    if (!isRecord(claims) || !isRecord(dates)) throw new Error("Invalid collection lookup tables");
    function index(name, id) {
      if (!Number.isInteger(id) || id < 0 || id >= raw[name].length) throw new Error(`Invalid ${name} reference`);
      return raw[name][id];
    }
    function record(name, id) {
      const value = index(name, id);
      if (!isRecord(value)) throw new Error(`Invalid ${name} reference`);
      return value;
    }
    for (const name of tables.filter(name => name.endsWith("contexts") || name === "discovery_records")) {
      raw[name].forEach((_, id) => record(name, id));
    }
    for (const coordinate of raw.coordinates) {
      if (!Array.isArray(coordinate) || typeof coordinate[0] !== "string") throw new Error("Invalid coordinate");
    }
    for (const date of Object.values(dates)) if (!isRecord(date)) throw new Error("Invalid date record");
    function dateReference(id) {
      if ((typeof id !== "string" && typeof id !== "number") || !Object.hasOwn(dates, id)) {
        throw new Error("Dangling date reference");
      }
    }
    function claimParts(id) {
      const packed = claims[id];
      if (normalized) return [packed, packed];
      return [record("claim_contexts", packed[compact ? 1 : 0]), packed[compact ? 2 : 1]];
    }
    function claimField(id, field) {
      const [context, details] = claimParts(id);
      if (compact && claims[id][0] === "ntvmr_index_v1") return field === "claim_id" ? Number(id) : context[field];
      return Object.hasOwn(details, field) ? details[field] : context[field];
    }
    const claimIdentifiers = new Set();
    for (const [id, packed] of Object.entries(claims)) {
      if (normalized) {
        if (!isRecord(packed)) throw new Error("Invalid claim record");
      } else {
        if (!Array.isArray(packed) || packed.length !== (compact ? 3 : 2)) throw new Error("Invalid packed claim");
        const [context, details] = claimParts(id);
        let keys;
        if (compact && packed[0] === "ntvmr_index_v1") {
          if (!/^(?:0|-?[1-9][0-9]*)$/.test(id) || !Number.isSafeInteger(Number(id)) || String(Number(id)) !== id ||
              !Array.isArray(details) || details.length !== 4 || !Number.isSafeInteger(details[3]) || details[3] < 0 ||
              !Number.isSafeInteger(context.doc_id) || !Number.isSafeInteger(details[2])) {
            throw new Error("Invalid compact index claim");
          }
          keys = ["claim_id", "source_ref", "page_id", "reported", "source_locator"];
        } else {
          if (compact && packed[0] !== "literal") throw new Error("Invalid claim encoding");
          if (!isRecord(details)) throw new Error("Invalid packed claim");
          keys = Object.keys(details);
        }
        if (keys.some(key => Object.hasOwn(context, key))) throw new Error("Packed claim overrides its context");
      }
      const identifier = claimField(id, "claim_id");
      if (identifier !== undefined) claimIdentifiers.add(jsonKey(identifier));
    }
    function validateClaimIds(ids) {
      if (!Array.isArray(ids)) throw new Error("Invalid event claim references");
      if (ids.some(id => !claimIdentifiers.has(jsonKey(id)))) throw new Error("Dangling event claim reference");
    }
    function coverageContext(key) {
      if (normalized) return key;
      return compact ? record("coverage_contexts", index("coverage_records", key)[0]) : record("coverage_records", key);
    }
    function coverageClaims(key) {
      return normalized ? key.claims : compact ? index("coverage_records", key)[1] : coverageContext(key).claims;
    }
    function validatePair(context, ids) {
      if (!isRecord(context) || !Array.isArray(ids) || !Array.isArray(context.date_assessments)) {
        throw new Error("Invalid coverage record");
      }
      for (const id of ids) {
        if (typeof id !== "string" || !Object.hasOwn(claims, id)) throw new Error("Dangling coverage claim reference");
        if (claimField(id, "assertion") === "present" && claimField(id, "claim_id") === undefined) {
          throw new Error("Missing coverage claim identifier");
        }
      }
      context.date_assessments.forEach(dateReference);
    }
    if (compact) for (const context of raw.coverage_contexts) {
      if (Object.hasOwn(context, "claims")) throw new Error("Coverage context contains claims");
      validatePair(context, []);
    }
    if (!normalized) raw.coverage_records.forEach((packed, id) => {
      if (compact && (!Array.isArray(packed) || packed.length !== 2 || !Array.isArray(packed[1]))) {
        throw new Error("Invalid packed coverage record");
      }
      validatePair(coverageContext(id), coverageClaims(id));
    });
    const coverageIndex = id => { index("coverage_records", id); };
    if (sparse) for (const vector of raw.coverage_defaults) {
      if (!Array.isArray(vector)) throw new Error("Invalid coverage default vector");
      vector.forEach(coverageIndex);
    }
    function validateEncoding(encoding) {
      if (Array.isArray(encoding) && encoding.length === 2 && encoding[0] === "dense" && Array.isArray(encoding[1])) {
        encoding[1].forEach(coverageIndex);
      } else if (sparse && Array.isArray(encoding) && encoding.length === 3 && encoding[0] === "sparse" && Array.isArray(encoding[2])) {
        const vector = index("coverage_defaults", encoding[1]);
        let previous = -1;
        for (const override of encoding[2]) {
          if (!Array.isArray(override) || override.length !== 2) throw new Error("Invalid coverage override");
          const [position, id] = override;
          if (!Number.isInteger(position) || position <= previous || position >= vector.length) throw new Error("Invalid coverage override position");
          coverageIndex(id); previous = position;
        }
      } else throw new Error("Invalid coverage encoding");
    }
    function row(ref) {
      return shared ? record("observation_contexts", raw.observations[ref][0]) : raw.observations[ref];
    }
    function* coverageKeys(ref) {
      if (!shared) {yield* row(ref).reported_coverage; return;}
      const encoding = raw.observations[ref][1];
      if (encoding[0] === "dense") {yield* encoding[1]; return;}
      const vector = raw.coverage_defaults[encoding[1]], overrides = encoding[2];
      let next = 0;
      for (let position = 0; position < vector.length; position++) {
        if (overrides[next]?.[0] === position) yield overrides[next++][1];
        else yield vector[position];
      }
    }
    function alternatives(ref) {
      const context = row(ref);
      return shared ? record("ranking_templates", context.dating_alternatives) : context.dating_alternatives;
    }
    function* rankingEvents(value) {
      if (!isRecord(value) || !Array.isArray(value.combinations)) throw new Error("Invalid ranking template");
      for (const combo of value.combinations) {
        if (!isRecord(combo) || !Array.isArray(combo.assessments) || !isRecord(combo.scenarios)) throw new Error("Invalid ranking combination");
        combo.assessments.forEach(dateReference);
        for (const events of Object.values(combo.scenarios)) {
          if (!Array.isArray(events)) throw new Error("Invalid ranking scenario");
          for (const event of events) {
            if (!isRecord(event) || !Object.hasOwn(event, "witness_id") || !Number.isFinite(event.event_year)) throw new Error("Invalid ranking event");
            dateReference(event.assessment_id);
            yield event;
          }
        }
      }
    }
    function pairFor(ref, witness) {
      let found, matches = 0;
      for (const key of coverageKeys(ref)) {
        const context = coverageContext(key);
        if (Object.hasOwn(context, "witness_id") && jsonKey(context.witness_id) === jsonKey(witness)) {found = key; matches++;}
      }
      if (matches !== 1) throw new Error("Missing or ambiguous coverage pair reference");
      return found;
    }
    function presentIds(key) {
      return coverageClaims(key).filter(id => claimField(id, "assertion") === "present").map(id => claimField(id, "claim_id"));
    }
    const pairWitnesses = new WeakMap();
    function validateRanking(value) {
      const witnesses = new Map();
      for (const event of rankingEvents(value)) {
        if (!shared) {validateClaimIds(event.coverage_claim_ids); continue;}
        const tag = event.coverage_claim_ids;
        if (Array.isArray(tag) && tag.length === 1 && tag[0] === "pair") witnesses.set(jsonKey(event.witness_id), event.witness_id);
        else if (Array.isArray(tag) && tag.length === 2 && tag[0] === "literal") validateClaimIds(tag[1]);
        else throw new Error("Invalid event claim encoding");
      }
      pairWitnesses.set(value, [...witnesses.values()]);
    }
    if (shared) {
      raw.ranking_templates.forEach(validateRanking);
      for (const context of raw.observation_contexts) {
        if (Object.hasOwn(context, "reported_coverage")) throw new Error("Observation context contains coverage");
        record("discovery_records", context.discovery);
        record("ranking_templates", context.dating_alternatives);
      }
    }
    for (const [ref, packed] of Object.entries(raw.observations)) {
      if (shared) {
        if (!Array.isArray(packed) || packed.length !== 2) throw new Error("Invalid packed observation");
        row(ref); validateEncoding(packed[1]);
        for (const witness of pairWitnesses.get(alternatives(ref))) pairFor(ref, witness);
      } else {
        if (!isRecord(packed) || !Array.isArray(packed.reported_coverage)) throw new Error("Invalid packed observation");
        if (normalized) {
          if (!isRecord(packed.discovery)) throw new Error("Invalid discovery record");
          packed.reported_coverage.forEach(pair => validatePair(pair, pair?.claims));
        } else {
          packed.reported_coverage.forEach(coverageIndex);
          record("discovery_records", packed.discovery);
        }
        validateRanking(packed.dating_alternatives);
      }
    }
    freezeJSON(raw);
    const data = freezeJSON(Object.fromEntries(Object.entries(raw).filter(([key]) =>
      !tables.includes(key) && !["observations", "claims", "dates"].includes(key))));
    const chartViews = new WeakMap(), claimCache = new Map();
    let cachedRef, cachedObservation, observationDecodes = 0, coverageDecodes = 0, chartTemplates = 0;
    function chartView(value) {
      if (!chartViews.has(value)) {
        chartTemplates++;
        chartViews.set(value, freezeJSON({...value, combinations: value.combinations.map(combo => ({...combo,
          scenarios: Object.fromEntries(Object.entries(combo.scenarios).map(([side, events]) => [side,
            events.map(({coverage_claim_ids, ...event}) => event)]))}))}));
      }
      return chartViews.get(value);
    }
    function claim(id) {
      if (!Object.hasOwn(claims, id)) return undefined;
      id = String(id);
      if (normalized) return claims[id];
      if (!claimCache.has(id)) {
        const [context, details] = claimParts(id);
        let restored = details;
        if (compact && claims[id][0] === "ntvmr_index_v1") {
          const [content, osis, page, locator] = details;
          restored = {claim_id: Number(id), source_ref: osis, page_id: page,
            reported: {docID: context.doc_id, indexContent: content, osisID: osis, pageID: page},
            source_locator: `data.indexContents.indexContent[${locator}]`};
        }
        claimCache.set(id, freezeJSON({...context, ...restored}));
      }
      return claimCache.get(id);
    }
    function observation(ref) {
      if (ref === cachedRef) return cachedObservation;
      cachedRef = ref; cachedObservation = null;
      if (!Object.hasOwn(raw.observations, ref)) return null;
      if (normalized) return (cachedObservation = row(ref));
      observationDecodes++;
      const context = copyJSON(row(ref));
      const pairs = [...coverageKeys(ref)].map(key => {
        coverageDecodes++;
        return {...copyJSON(coverageContext(key)), claims: copyJSON(coverageClaims(key))};
      });
      const ranking = copyJSON(alternatives(ref));
      if (shared) for (const event of rankingEvents(ranking)) {
        const tag = event.coverage_claim_ids;
        event.coverage_claim_ids = tag[0] === "pair" ? presentIds(pairFor(ref, event.witness_id)) : tag[1];
      }
      cachedObservation = freezeJSON({...context, reported_coverage: pairs, dating_alternatives: ranking,
        discovery: copyJSON(record("discovery_records", context.discovery))});
      return cachedObservation;
    }
    const store = Object.freeze({data, formatVersion: version, dateIds: Object.freeze(Object.keys(dates)),
      hasObservation: ref => Object.hasOwn(raw.observations, ref),
      summary(ref) {
        if (!Object.hasOwn(raw.observations, ref)) return null;
        const context = row(ref), totals = {present: 0, unknown: 0, contested: 0, absent: 0};
        for (const key of coverageKeys(ref)) {
          const state = coverageContext(key).state;
          totals[state] = (totals[state] || 0) + 1;
        }
        return freezeJSON({editorial_status: context.editorial_status, ranking_state: context.ranking_state,
          discovery: normalized ? context.discovery : record("discovery_records", context.discovery),
          contested: totals.contested > 0, coverage_totals: totals});
      },
      chartAlternatives: ref => Object.hasOwn(raw.observations, ref) ? chartView(alternatives(ref)) : null,
      // Inspect referenced templates once; unused valid templates do not change scale.
      *chartRecords() {
        const seen = new Set();
        for (const ref of Object.keys(raw.observations)) {
          const value = alternatives(ref);
          if (!seen.has(value)) {seen.add(value); yield chartView(value);}
        }
      },
      claim, date: id => Object.hasOwn(dates, id) ? dates[id] : undefined, observation,
      diagnostics: () => Object.freeze({observationDecodes, coverageDecodes, chartTemplates,
        cachedObservations: cachedObservation ? 1 : 0, cachedClaims: claimCache.size})});
    stores.add(store);
    return store;
  }

  function expandData(data) {
    if (data?.format_version === 4) return createDataStore(data).expandData();
    const isRecord = value => value && typeof value === "object" && !Array.isArray(value);
    if (!isRecord(data) || !Array.isArray(data.coordinates) || !isRecord(data.observations)) {
      throw new Error("Unsupported collection data");
    }
    if (data.format_version === 1) return copyJSON(data);
    // Numeric version 3 is the complete production schema. Retained private
    // candidate markers remain readable for offline compatibility checks.
    const phase3 = data.format_version === 3 || data.format_version === "3-phase3";
    const phase2 = data.format_version === "3-phase2" || phase3;
    const sharedObservations = data.format_version === "3-phase1" || phase2;
    if (data.format_version !== 2 && !sharedObservations) throw new Error("Unsupported collection data");
    const names = ["claim_contexts", "coverage_records", "discovery_records"];
    if (sharedObservations) names.push("ranking_templates", "observation_contexts");
    if (phase2) names.push("coverage_contexts");
    if (phase3) names.push("coverage_defaults");
    if (names.some(name => !Array.isArray(data[name])) || !isRecord(data.claims)) {
      throw new Error("Missing collection record tables");
    }
    function copyJSON(value) {
      if (Array.isArray(value)) return value.map(copyJSON);
      if (!isRecord(value)) return value;
      const copy = {...value};
      for (const key of Object.keys(copy)) {
        if (copy[key] && typeof copy[key] === "object") copy[key] = copyJSON(copy[key]);
      }
      return copy;
    }
    function record(name, index) {
      if (!Number.isInteger(index) || index < 0 || index >= data[name].length || !isRecord(data[name][index])) {
        throw new Error(`Invalid ${name} reference`);
      }
      // Observations stay independent even when their transfer records are shared.
      return copyJSON(data[name][index]);
    }
    const claims = Object.fromEntries(Object.entries(data.claims).map(([id, packed]) => {
      let context, details;
      if (phase2) {
        // Claims: ["ntvmr_index_v1", contextIndex, [indexContent, osisID,
        // pageID, locatorIndex]] or ["literal", contextIndex, completeDetails].
        if (!Array.isArray(packed) || packed.length !== 3) throw new Error("Invalid packed claim");
        const [tag, index, values] = packed;
        context = record("claim_contexts", index);
        if (tag === "literal" && isRecord(values)) details = copyJSON(values);
        else if (tag === "ntvmr_index_v1") {
          const claimId = Number(id);
          if (!/^(?:0|-?[1-9][0-9]*)$/.test(id) || !Number.isSafeInteger(claimId) || String(claimId) !== id ||
              !Array.isArray(values) || values.length !== 4 || !Number.isSafeInteger(values[3]) || values[3] < 0 ||
              !Number.isSafeInteger(context.doc_id) || !Number.isSafeInteger(values[2])) {
            throw new Error("Invalid compact index claim");
          }
          const [content, osis, page, locator] = copyJSON(values);
          details = {claim_id: claimId, source_ref: osis, page_id: page,
            reported: {docID: context.doc_id, indexContent: content, osisID: copyJSON(osis), pageID: page},
            source_locator: `data.indexContents.indexContent[${locator}]`};
        } else throw new Error("Invalid claim encoding");
      } else {
        if (!Array.isArray(packed) || packed.length !== 2 || !isRecord(packed[1])) throw new Error("Invalid packed claim");
        context = record("claim_contexts", packed[0]);
        details = sharedObservations ? copyJSON(packed[1]) : packed[1];
      }
      if (Object.keys(details).some(key => Object.hasOwn(context, key))) {
        throw new Error("Packed claim overrides its context");
      }
      return [id, {...context, ...details}];
    }));
    if (sharedObservations) {
      // Observations: [contextIndex, ["dense", coverageRecordIndices]] or
      // [contextIndex, ["sparse", defaultsIndex, [[position, recordIndex], ...]]].
      // Sparse overrides have strictly increasing positions. Context
      // discovery/dating_alternatives are table indices. Ranking event claim
      // lists: ["pair"] or ["literal", originalIds]. All other fields survive.
      const orderedJSON = value => Array.isArray(value) ? value.map(orderedJSON) :
        isRecord(value) ? Object.fromEntries(Object.keys(value).sort().map(key => [key, orderedJSON(value[key])])) : value;
      const jsonKey = value => JSON.stringify(orderedJSON(value));
      const claimIds = new Set(Object.values(claims).filter(claim => Object.hasOwn(claim, "claim_id"))
        .map(claim => jsonKey(claim.claim_id)));
      function validateEventIds(ids) {
        if (!Array.isArray(ids)) throw new Error("Invalid event claim references");
        if (ids.some(id => !claimIds.has(jsonKey(id)))) throw new Error("Dangling event claim reference");
      }
      function presentClaimIds(pair) {
        if (!isRecord(pair) || !Array.isArray(pair.claims)) throw new Error("Invalid coverage record");
        const ids = [];
        for (const id of pair.claims) {
          if (typeof id !== "string" || !Object.hasOwn(claims, id)) throw new Error("Dangling coverage claim reference");
          const claim = claims[id];
          if (claim.assertion === "present") {
            if (!Object.hasOwn(claim, "claim_id")) throw new Error("Missing coverage claim identifier");
            ids.push(claim.claim_id);
          }
        }
        return ids;
      }
      function pairClaimIds(pairs, witness) {
        const matches = pairs.filter(pair => Object.hasOwn(pair, "witness_id") && jsonKey(pair.witness_id) === jsonKey(witness));
        if (matches.length !== 1) throw new Error("Missing or ambiguous coverage pair reference");
        return presentClaimIds(matches[0]);
      }
      function* rankingEvents(alternatives) {
        if (!isRecord(alternatives) || !Array.isArray(alternatives.combinations)) throw new Error("Invalid ranking template");
        for (const combination of alternatives.combinations) {
          if (!isRecord(combination) || !isRecord(combination.scenarios)) throw new Error("Invalid ranking combination");
          for (const events of Object.values(combination.scenarios)) {
            if (!Array.isArray(events)) throw new Error("Invalid ranking scenario");
            for (const event of events) {
              if (!isRecord(event) || !Object.hasOwn(event, "witness_id")) throw new Error("Invalid ranking event");
              yield event;
            }
          }
        }
      }
      const coverageRecords = data.coverage_records.map(packed => {
        let pair = packed;
        if (phase2) {
          // Coverage: [coverageContextIndex, orderedClaimIdStrings]. Contexts
          // contain every other field, including all date assessment IDs.
          if (!Array.isArray(packed) || packed.length !== 2 || !Array.isArray(packed[1])) {
            throw new Error("Invalid packed coverage record");
          }
          const context = record("coverage_contexts", packed[0]);
          if (Object.hasOwn(context, "claims")) throw new Error("Coverage context contains claims");
          pair = {...context, claims: copyJSON(packed[1])};
        }
        presentClaimIds(pair);
        return pair;
      });
      function validateCoverageIndex(index) {
        if (!Number.isInteger(index) || index < 0 || index >= coverageRecords.length) {
          throw new Error("Invalid coverage_records reference");
        }
      }
      function coverageRecord(index) {
        validateCoverageIndex(index);
        return copyJSON(coverageRecords[index]);
      }
      if (phase3) {
        // Check unused defaults too, without creating observations for any
        // coordinate omitted from the stored observation keys.
        for (const vector of data.coverage_defaults) {
          if (!Array.isArray(vector)) throw new Error("Invalid coverage default vector");
          vector.forEach(validateCoverageIndex);
        }
      }
      const observations = Object.fromEntries(Object.entries(data.observations).map(([ref, packed]) => {
        if (!Array.isArray(packed) || packed.length !== 2) throw new Error("Invalid packed observation");
        const row = record("observation_contexts", packed[0]), encoding = packed[1];
        if (Object.hasOwn(row, "reported_coverage")) throw new Error("Observation context contains coverage");
        let vector;
        if (Array.isArray(encoding) && encoding.length === 2 && encoding[0] === "dense" && Array.isArray(encoding[1])) {
          vector = encoding[1];
        } else if (phase3 && Array.isArray(encoding) && encoding.length === 3 && encoding[0] === "sparse" && Array.isArray(encoding[2])) {
          const index = encoding[1];
          if (!Number.isInteger(index) || index < 0 || index >= data.coverage_defaults.length) {
            throw new Error("Invalid coverage_defaults reference");
          }
          vector = data.coverage_defaults[index].slice();
          let previous = -1;
          for (const override of encoding[2]) {
            if (!Array.isArray(override) || override.length !== 2) throw new Error("Invalid coverage override");
            const [position, recordIndex] = override;
            if (!Number.isInteger(position) || position <= previous || position >= vector.length) {
              throw new Error("Invalid coverage override position");
            }
            validateCoverageIndex(recordIndex);
            vector[position] = recordIndex;
            previous = position;
          }
        } else throw new Error("Invalid coverage encoding");
        const pairs = vector.map(coverageRecord);
        row.discovery = record("discovery_records", row.discovery);
        const alternatives = record("ranking_templates", row.dating_alternatives);
        for (const event of rankingEvents(alternatives)) {
          const tag = event.coverage_claim_ids;
          let ids;
          if (Array.isArray(tag) && tag.length === 1 && tag[0] === "pair") ids = pairClaimIds(pairs, event.witness_id);
          else if (Array.isArray(tag) && tag.length === 2 && tag[0] === "literal") ids = tag[1];
          else throw new Error("Invalid event claim encoding");
          validateEventIds(ids);
          event.coverage_claim_ids = copyJSON(ids);
        }
        return [ref, {...row, reported_coverage: pairs, dating_alternatives: alternatives}];
      }));
      const rest = Object.fromEntries(Object.entries(data).filter(([key]) => !names.includes(key) && key !== "claims" && key !== "observations"));
      return {...copyJSON(rest), format_version: 1, claims, observations};
    }
    const observations = Object.fromEntries(Object.entries(data.observations).map(([ref, row]) => {
      if (!isRecord(row) || !Array.isArray(row.reported_coverage)) throw new Error("Invalid packed observation");
      return [ref, {...row,
        reported_coverage: row.reported_coverage.map(index => record("coverage_records", index)),
        discovery: record("discovery_records", row.discovery)}];
    }));
    const {claim_contexts, coverage_records, discovery_records, ...rest} = data;
    return copyJSON({...rest, format_version: 1, claims, observations});
  }

  function hitIndex(x, width, scrollLeft, totalWidth, count) {
    return clamp(Math.floor((clamp(x, 0, width) + scrollLeft) / totalWidth * count), 0, count - 1);
  }

  // Simultaneous events increase the count together. A range below the first
  // event is intentionally empty; unknown years never create an event.
  function segments(events, maximum) {
    const grouped = new Map();
    for (const event of events) grouped.set(event.event_year, (grouped.get(event.event_year) || 0) + 1);
    const years = [...grouped.keys()].sort((a, b) => a - b);
    let count = 0;
    return years.map((year, index) => {
      count += grouped.get(year);
      return {from: year, to: years[index + 1] ?? maximum, count: Math.min(count, 5)};
    });
  }

  function createModel(input) {
    if (models.has(input)) return input;
    const store = createDataStore(input), data = store.data;
    if (!data.coordinates.length) throw new Error("Unsupported explorer data");
    const indices = new Map(data.coordinates.map((row, index) => [row[0], index]));
    const choices = new Map();
    const dates = store.dateIds.map(store.date).sort((a, b) => Number(a.assessment_id) - Number(b.assessment_id));
    for (const date of dates) {
      if (date.status !== "valid") continue;
      if (!choices.has(date.witness_id)) choices.set(date.witness_id, []);
      choices.get(date.witness_id).push(date);
    }
    const selection = new Map([...choices].map(([id, items]) => [id, String(items[0].assessment_id)]));
    const books = BOOKS.map(([code, name, short]) => {
      const first = data.coordinates.findIndex(row => row[0].startsWith(code + "."));
      let end = first;
      while (end < data.coordinates.length && data.coordinates[end]?.[0].startsWith(code + ".")) end++;
      return {code, name, short, first, end};
    }).filter(book => book.first >= 0);
    const labels = new Map(BOOKS.map(([code, name]) => [code, name]));
    const witnesses = new Map(data.documents.map(doc => [doc.witness_id,
      /^\d+$/.test(doc.label) ? `GA ${doc.label.padStart(2, "0")}` : doc.label]));
    let minimum = Infinity, maximum = -Infinity;
    for (const alternatives of store.chartRecords()) {
      for (const combo of alternatives.combinations) {
        for (const events of Object.values(combo.scenarios)) for (const event of events) {
          minimum = Math.min(minimum, event.event_year);
          maximum = Math.max(maximum, event.event_year);
        }
      }
    }
    const hasEvents = Number.isFinite(minimum);
    minimum = hasEvents ? Math.floor((minimum - 10) / 50) * 50 : 0;
    maximum = hasEvents ? Math.ceil((maximum + 10) / 50) * 50 : 500;
    function label(index) {
      const [book, chapter, verse] = data.coordinates[index][0].split(".");
      return `${labels.get(book) || book} ${chapter}:${verse}`;
    }
    function lookup(value) {
      const match = value.trim().match(/^(.+?)[.\s]+(\d+)[:.](\d+)$/);
      if (!match) return -1;
      const book = BOOKS.find(parts => parts.some(part => normalize(part) === normalize(match[1])));
      return book ? (indices.get(`${book[0]}.${Number(match[2])}.${Number(match[3])}`) ?? -1) : -1;
    }
    function cell(index, scenario) {
      const [ref, editorial] = data.coordinates[index];
      const summary = store.summary(ref);
      const status = summary?.editorial_status || editorial;
      const filters = data.metadata.filters;
      if ((status === "omitted" && !filters.include_omitted) ||
          (status === "bracketed" && !filters.include_bracketed)) {
        return {ref, state: "filtered", events: []};
      }
      if (!summary) return {ref, state: "uncollected", events: []};
      const alternatives = store.chartAlternatives(ref);
      const combo = alternatives.combinations.find(item => item.assessments.every(id =>
        selection.get(store.date(id).witness_id) === String(id)));
      const events = combo?.scenarios[scenario] || [];
      return {state: alternatives.state === "too_many_combinations" ? "too_many_combinations" :
        (!combo && alternatives.combinations.length ? "unavailable_combination" : events.length ? "dated" : "no_date"),
        ref, events, contested: summary.contested};
    }
    function discovery(index) {
      const ref = data.coordinates[index][0], meta = data.metadata.discovery;
      const reported = store.summary(ref)?.discovery;
      const book = ref.split(".")[0];
      const scopes = (meta?.scopes || [meta]).filter(item => item?.definition?.book === book ||
        item?.definition?.books?.includes(book));
      if (!scopes.length) {
        return {state: "not_searched", text: "Witness discovery has not been assessed for this verse. Rankings cover collected witnesses only."};
      }
      const incomplete = scopes.find(item => item.search_state !== "complete");
      const state = reported?.state || (incomplete ? "search_incomplete" :
        scopes.some(item => item.candidate_collection_state !== "complete") ? "candidate_collection_incomplete" : "bounded_search_complete");
      const count = new Set(scopes.flatMap(item => item.candidate_ids)).size;
      const pending = new Set(scopes.flatMap(item => item.pending_candidate_ids)).size;
      const cutoffs = [...new Set(scopes.map(item => item.definition.earliest_date_before).filter(value => value != null))];
      const eligible = new Set(scopes.flatMap(item => item.eligible_candidate_ids || item.candidate_ids)).size;
      const excluded = new Set(scopes.flatMap(item => item.date_excluded_candidate_ids || [])).size;
      const dateScope = cutoffs.length ? ` Collection date cutoff${cutoffs.length === 1 ? "" : "s"}: ranges must start before ${cutoffs.join(" or ")} CE; unknown dates and retained earlier estimates remain eligible. ${excluded} candidates excluded in these date-filtered scopes. Captured reports are preserved; fewer than five witnesses per verse is acceptable.` : "";
      const catalogue = scopes.some(item => item.definition.scope_type === "catalogue_range");
      const search = catalogue ? "catalogue search" : "book search";
      const pool = catalogue ? "Catalogue membership does not establish verse contents. Unindexed contents remain unknown. Rankings cover collected witnesses only; exhaustive discovery is not established." :
        "Other catalogue ranges and unindexed witnesses remain outside this search. Rankings cover collected witnesses only.";
      const candidates = cutoffs.length ? `${eligible} eligible search candidates` : `${count} search candidates`;
      const text = (state === "bounded_search_complete" ? `Bounded ${search} complete; all ${candidates} collected. ${pool}` :
        state === "candidate_collection_incomplete" ? `Bounded ${search} complete; ${pending} of ${candidates} await metadata or contents collection. ${pool}` :
        `Bounded ${search} ${(incomplete?.search_state || "incomplete").replaceAll("_", " ")}; ${count} candidates identified so far. ${pool}`) + dateScope;
      return {state, text};
    }
    const model = {data, store, indices, books, choices, selection, minimum, maximum, hasEvents, label, lookup, cell,
      discovery, witness: id => witnesses.get(id) || id};
    models.add(model);
    return model;
  }

  function mount(root, data, options = {}) {
    const model = createModel(data);
    data = model.data;
    const el = name => root.querySelector(`[data-el="${name}"]`);
    const doc = root.ownerDocument;
    const view = doc.defaultView;
    const abort = new view.AbortController();
    const on = (node, event, listener) => node.addEventListener(event, listener, {signal: abort.signal});
    const node = (tag, text, className) => {
      const result = doc.createElement(tag);
      if (text != null) result.textContent = text;
      if (className) result.className = className;
      return result;
    };
    const appendText = (parent, tag, text, className) => parent.appendChild(node(tag, text, className));
    const link = (parent, citation, title) => {
      const match = (citation || "").match(/https?:\/\/[^\s;,]+/);
      if (!match) return appendText(parent, "span", citation || "Source unavailable");
      const a = node("a", title || citation);
      a.href = match[0].replace(/[.)]+$/, "");
      a.target = "_blank"; a.rel = "noopener noreferrer";
      parent.append(a);
      return a;
    };
    const canvas = el("canvas"), context = canvas.getContext("2d");
    const scroll = el("scroll"), spacer = el("spacer");
    let scenario = "optimistic", zoom = 1, pinned = false, frame = 0;
    let width = 1, height = 320, cachedCells = [], runs = [], hasSize = false;
    let selected = data.coordinates.findIndex(([ref]) => model.store.hasObservation(ref));
    selected = Math.max(0, selected);
    const totalWidth = () => width * zoom;
    const plotTop = 32, plotBottom = () => height - 35;
    const y = year => plotTop + (model.maximum - year) / (model.maximum - model.minimum) * (plotBottom() - plotTop);
    const refreshCells = () => {
      cachedCells = data.coordinates.map((_, i) => model.cell(i, scenario));
      // Join visually identical adjacent columns. This preserves their exact
      // count steps and avoids repeated subpixel alpha blending at corpus scale.
      runs = [];
      cachedCells.forEach((cell, index) => {
        const key = JSON.stringify([cell.state, !!cell.contested, cell.events.map(e => e.event_year)]);
        const last = runs.at(-1);
        if (last?.key === key) last.end = index + 1;
        else runs.push({first: index, end: index + 1, cell, key});
      });
    };
    const scheduleDraw = () => {if (!frame) frame = view.requestAnimationFrame(() => {frame = 0; draw();});};

    function draw() {
      const count = data.coordinates.length, unit = totalWidth() / count, offset = scroll.scrollLeft;
      const bottom = plotBottom(), plotHeight = bottom - plotTop;
      context.clearRect(0, 0, width, height);
      context.fillStyle = "#edf0eb"; context.fillRect(0, plotTop, width, plotHeight);
      const first = clamp(Math.floor(offset / unit), 0, count - 1);
      const last = clamp(Math.ceil((offset + width) / unit), 0, count);
      for (const run of runs) {
        if (run.end <= first || run.first >= last) continue;
        const cell = run.cell, x = Math.max(0, run.first * unit - offset);
        const span = Math.min(width, run.end * unit - offset) - x;
        if (cell.state === "uncollected") continue;
        context.fillStyle = cell.state === "filtered" ? "#e8e4ef" : "#fbfcfa";
        context.fillRect(x, plotTop, span, plotHeight);
        if (cell.events.length) {
          for (const band of segments(cell.events, model.maximum)) {
            context.fillStyle = COLORS[band.count - 1];
            context.fillRect(x, y(band.to), span, Math.max(0, y(band.from) - y(band.to)));
          }
        } else if (cell.state !== "filtered") {
          context.save(); context.beginPath(); context.rect(x, plotTop, span, plotHeight); context.clip();
          context.fillStyle = "#eef2f0"; context.fillRect(x, plotTop, span, plotHeight);
          context.strokeStyle = "#cbd6d0"; context.lineWidth = 1;
          context.beginPath();
          for (let p = -plotHeight; p < span; p += 7) {
            context.moveTo(x + p, bottom); context.lineTo(x + p + plotHeight, plotTop);
          }
          context.stroke(); context.restore();
        }
        if (cell.contested) {context.fillStyle = "#bb754b"; context.fillRect(x, bottom - 5, span, 5);}
      }
      if (unit >= 4) {
        context.fillStyle = "#ffffff66";
        for (let i = first; i < last; i++) context.fillRect(i * unit - offset, plotTop, .5, plotHeight);
      }
      context.lineWidth = 1; context.strokeStyle = "#71857325";
      for (let tick = 0; tick <= 4; tick++) {
        const py = y(model.minimum + (model.maximum - model.minimum) * tick / 4);
        context.beginPath(); context.moveTo(0, py); context.lineTo(width, py); context.stroke();
      }
      context.font = "10px system-ui"; context.textBaseline = "middle";
      let labelRight = -5;
      for (const book of model.books) {
        const x = book.first * unit - offset, right = book.end * unit - offset;
        if (right < 0 || x > width) continue;
        context.strokeStyle = "#97aa9b66";
        context.beginPath(); context.moveTo(x, plotTop); context.lineTo(x, bottom + 5); context.stroke();
        const available = Math.min(width, right) - Math.max(0, x);
        const text = available > context.measureText(book.name).width + 12 ? book.name : book.short;
        const textWidth = context.measureText(text).width;
        const center = (Math.max(0, x) + Math.min(width, right)) / 2;
        if (center - textWidth / 2 > labelRight + 3 && available >= textWidth + 2) {
          context.fillStyle = "#667b6b"; context.textAlign = "center";
          context.fillText(text, center, bottom + 18); labelRight = center + textWidth / 2;
        }
      }
      if (unit > 2) {
        let previousChapter = "";
        context.font = "9px system-ui"; context.textAlign = "left";
        for (let i = first; i < last; i++) {
          const ref = data.coordinates[i][0].split("."), chapter = ref.slice(0, 2).join(".");
          if (chapter !== previousChapter) {
            const x = i * unit - offset;
            context.fillStyle = "#7c8b7f"; context.fillText(`Ch ${ref[1]}`, x + 3, 22);
            previousChapter = chapter;
          }
        }
      }
      const x = (selected + .5) * unit - offset;
      el("selection-label").hidden = x < 0 || x > width;
      if (x >= 0 && x <= width) {
        context.strokeStyle = "#254f40"; context.lineWidth = 1.5;
        context.beginPath(); context.moveTo(x, plotTop); context.lineTo(x, bottom + 3); context.stroke();
        const label = el("selection-label");
        label.style.left = `${clamp(x - label.offsetWidth / 2, 0, Math.max(0, width - label.offsetWidth))}px`;
      }
    }

    function resize() {
      const center = (scroll.scrollLeft + width / 2) / totalWidth();
      width = Math.max(1, canvas.clientWidth); height = canvas.clientHeight;
      const dpr = view.devicePixelRatio || 1;
      canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      spacer.style.width = `${totalWidth()}px`;
      if (hasSize) scroll.scrollLeft = Math.max(0, center * totalWidth() - width / 2);
      hasSize = true;
      el("axis").replaceChildren(node("span", "CE ↑", "axis-unit"));
      for (let tick = 0; tick <= 4; tick++) {
        const year = model.minimum + (model.maximum - model.minimum) * tick / 4;
        const label = node("span", Math.round(year)); label.style.top = `${y(year)}px`; el("axis").append(label);
      }
      updateZoomLabel(); scheduleDraw();
    }

    function updateZoomLabel() {
      el("zoom-label").textContent = zoom === 1 ? "Full GNT" : `${Math.round(zoom)}×`;
      el("zoom-out").disabled = zoom <= 1;
      el("zoom-in").disabled = zoom >= 128;
      el("resolution-note").textContent = totalWidth() / data.coordinates.length < 2 ?
        "Overview: several verses share a screen pixel. Zoom or enter a reference for precision." :
        "One column per verse. Scroll horizontally to move through the New Testament.";
    }

    function setZoom(value, center = selected) {
      zoom = clamp(value, 1, 128); spacer.style.width = `${totalWidth()}px`;
      scroll.scrollLeft = Math.max(0, (center + .5) / data.coordinates.length * totalWidth() - width / 2);
      updateZoomLabel(); scheduleDraw();
    }

    function ensureVisible() {
      const x = (selected + .5) / data.coordinates.length * totalWidth();
      if (x < scroll.scrollLeft || x > scroll.scrollLeft + width) scroll.scrollLeft = Math.max(0, x - width / 2);
    }

    function sourceRecord(parent, record, kind) {
      const section = node("div", null, "source-record");
      appendText(section, "strong", kind === "date" ? `Date: ${interval(record)} · ${record.original_notation || "notation not supplied"}` :
        `${record.assertion} · ${record.extent || "unspecified"} extent`);
      appendText(section, "p", record.provider);
      link(section, record.citation);
      appendText(section, "p", `Retrieved ${record.retrieved_at} · Field: ${record.source_locator}`);
      appendText(section, "p", record.qualifications || "No additional qualifications supplied.");
      appendText(section, "p", `Response ${record.source_response_id} · ${kind === "date" ? "Assessment " + record.assessment_id : "Claim " + record.claim_id}`);
      appendText(section, "code", `SHA-256 ${record.source_sha256}`);
      appendText(section, "pre", JSON.stringify(record.reported, null, 2));
      parent.append(section);
    }

    function renderClaims(ref) {
      const parent = el("claims"); parent.replaceChildren();
      const observation = model.store.observation(ref);
      if (!observation) return;
      if (observation.mapping_note) appendText(parent, "p", `Mapping: ${observation.mapping_note}`);
      if (observation.editorial_note) appendText(parent, "p", observation.editorial_note);
      if (observation.passage_citation) link(parent, observation.passage_citation);
      for (const pair of observation.reported_coverage) {
        appendText(parent, "h3", `${model.witness(pair.witness_id)} · ${pair.state}`);
        if (pair.unknown_reason) appendText(parent, "p", pair.unknown_reason.replaceAll("_", " "));
        if (pair.state === "contested") appendText(parent, "p", "Explicit incompatible source claims retained. Deferred; no presence event.");
        for (const id of pair.claims) sourceRecord(parent, model.store.claim(id), "coverage");
        for (const id of pair.date_assessments) sourceRecord(parent, model.store.date(id), "date");
        if (!pair.date_assessments.length) appendText(parent, "p", "No reported date assessment; unrankable.");
      }
    }

    function renderSelection() {
      const cell = cachedCells[selected], ref = model.label(selected);
      const observation = model.store.observation(cell.ref);
      el("selected-heading").textContent = ref;
      el("discovery-summary").textContent = model.discovery(selected).text;
      el("selection-label").textContent = ref;
      el("previous").disabled = selected === 0;
      el("next").disabled = selected === data.coordinates.length - 1;
      el("pin").setAttribute("aria-pressed", String(pinned));
      el("pin").textContent = pinned ? "Release verse" : "Hold verse";
      canvas.setAttribute("aria-valuenow", selected + 1);
      canvas.setAttribute("aria-valuetext", `${ref}: ${cell.state.replaceAll("_", " ")}`);
      const parent = el("witnesses"); parent.replaceChildren();
      el("source-details").hidden = !observation;
      let summary;
      if (cell.state === "uncollected" || cell.state === "filtered") {
        summary = cell.state === "filtered" ? "Excluded by this export’s edition filter. This says nothing about manuscript contents." :
          "Not collected in this dataset. No date or contents claim is made for this verse.";
        appendText(parent, "div", cell.state === "filtered" ? "This coordinate retains its place in the GNT. Change the export filters to include its reports." :
          "This verse has a place on the timeline. Its source summary will appear when reports are added to the dataset.", "empty-state");
      } else {
        const pairs = observation.reported_coverage;
        const totals = {present: 0, unknown: 0, contested: 0, absent: 0};
        for (const pair of pairs) totals[pair.state]++;
        const first = cell.events[0];
        summary = `${totals.present} reported present · ${totals.unknown} unknown · ${totals.contested} contested · ${totals.absent} reported absent.`;
        summary += first ? ` Earliest collected ${scenario} endpoint: ${first.event_year} CE (${model.witness(first.witness_id)}).` : " No dated presence event for this selection.";
        if (cell.state === "too_many_combinations") summary += ` ${observation.dating_alternatives.combination_count} date combinations exceed the export limit; no alternative selected.`;
        if (cell.state === "unavailable_combination") summary += " This combination of date choices is unavailable for this verse.";
        const order = [...pairs].sort((a, b) => {
          const rank = pair => cell.events.find(e => e.witness_id === pair.witness_id)?.rank ?? 999;
          return rank(a) - rank(b);
        });
        // Keep the immediate source summary brief even with a large collected set.
        for (const pair of order.slice(0, 5)) {
          const card = node("article", null, "witness-card"), top = node("div", null, "witness-top");
          appendText(top, "strong", model.witness(pair.witness_id));
          appendText(top, "span", pair.state === "present" ? "Reported present" : pair.state, `badge ${pair.state}`);
          card.append(top);
          const event = cell.events.find(e => e.witness_id === pair.witness_id);
          const dates = pair.date_assessments.map(model.store.date);
          const date = event ? model.store.date(event.assessment_id) : dates.find(d => String(d.assessment_id) === model.selection.get(pair.witness_id)) || dates[0];
          appendText(card, "p", date ? interval(date) : "Date not reported", "interval");
          appendText(card, "p", event ? `#${event.rank} · ${event.event_year} CE ${scenario} endpoint` :
            pair.state === "contested" ? "Deferred · excluded from presence counts" : pair.state === "present" ? "No ranked event in this selection" : "No presence event");
          if (dates.length > 1) appendText(card, "p", `${dates.length} reported date assessments · all retained below`);
          const claim = pair.claims.length ? model.store.claim(pair.claims[0]) : null;
          if (claim) {
            appendText(card, "p", `${claim.provider} · retrieved ${claim.retrieved_at.slice(0, 10)}`);
            link(card, claim.citation, "Contents source ↗");
          } else appendText(card, "p", "No explicit mapped contents report. Missing entries do not establish absence.");
          if (date) {appendText(card, "span", " · "); link(card, date.citation, "Date source ↗");}
          parent.append(card);
        }
        if (pairs.length > 5) appendText(parent, "p", `${pairs.length - 5} more witnesses in source details.`, "empty-state");
        if (!pairs.length) appendText(parent, "p", "No witness reports are available for this coordinate.", "empty-state");
      }
      el("summary").textContent = summary;
      if (el("source-details").open) renderClaims(cell.ref);
      else el("claims").replaceChildren();
      options.onSelect?.({ref: data.coordinates[selected][0], scenario, state: cell.state});
    }

    function select(index, hold = pinned, reveal = false) {
      const next = clamp(index, 0, data.coordinates.length - 1);
      if (next === selected && hold === pinned && !reveal) return;
      selected = next; pinned = hold;
      if (reveal) ensureVisible();
      renderSelection(); scheduleDraw();
    }

    function setScenario(value) {
      if (!["optimistic", "pessimistic"].includes(value)) throw new Error("Unknown scenario");
      scenario = value;
      for (const input of root.querySelectorAll('input[name="scenario"]')) input.checked = input.value === value;
      el("scenario-note").textContent = `${value === "optimistic" ? "Optimistic · lower" : "Pessimistic · upper"} endpoints of reported date ranges`;
      refreshCells(); renderSelection(); scheduleDraw();
    }

    for (const book of model.books) {
      const option = node("option", book.name); option.value = book.code; el("book").append(option);
    }
    for (const [value, label] of [[data.metadata.counts.verse_count, "verses collected"],
      [data.metadata.counts.witness_count, "distinct witnesses"], [model.books.length, "books on timeline"]]) {
      const stat = node("div", null, "stat"); appendText(stat, "strong", value.toLocaleString()); appendText(stat, "span", label); el("stats").append(stat);
    }
    for (const [witness, dates] of model.choices) {
      if (dates.length === 1) {appendText(el("date-choices"), "p", `${model.witness(witness)} · ${interval(dates[0])} · ${dates[0].provider}`); continue;}
      const label = node("label", model.witness(witness), "date-choice"), selectDate = node("select");
      for (const date of dates) {
        const option = node("option", `${interval(date)} · ${date.provider} · assessment ${date.assessment_id}`);
        option.value = date.assessment_id; selectDate.append(option);
      }
      on(selectDate, "change", () => {model.selection.set(witness, selectDate.value); refreshCells(); renderSelection(); scheduleDraw();});
      label.append(selectDate); el("date-choices").append(label);
    }
    if (!model.choices.size) appendText(el("date-choices"), "p", "No usable numeric date intervals in this export.");
    const scope = el("scope"), meta = data.metadata;
    const discoveries = (meta.discovery?.scopes || [meta.discovery]).filter(item => item?.definition);
    el("discovery-tag").textContent = discoveries.length ? "COLLECTED WITNESSES · BOUNDED DISCOVERY" :
      "COLLECTED WITNESSES · DISCOVERY NOT ASSESSED";
    appendText(scope, "p", meta.collection_scope);
    appendText(scope, "h3", "Witness discovery");
    for (const discovery of discoveries) {
      const scopeLabel = discovery.definition.book || `${discovery.definition.category || "Catalogue"} · ${discovery.definition.books.length} books`;
      appendText(scope, "p", `${scopeLabel}: document IDs ${discovery.definition.doc_id_min}–${discovery.definition.doc_id_max}. Search ${discovery.search_state}; candidate collection ${discovery.candidate_collection_state}.`);
      appendText(scope, "p", `Search candidates: ${discovery.candidate_ids.join(", ") || (discovery.search_state === "complete" ? "none returned" : "not established")}. Awaiting collection: ${discovery.pending_candidate_ids.join(", ") || (discovery.search_state === "complete" ? "none" : "not established")}.`);
      if (discovery.definition.earliest_date_before != null) {
        appendText(scope, "p", `Collection cutoff: earliest date before ${discovery.definition.earliest_date_before} CE. Date-excluded candidates: ${(discovery.date_excluded_candidate_ids || []).join(", ") || "none"}. Unknown dates remain eligible.`);
      }
      appendText(scope, "p", discovery.limitation);
      appendText(scope, "p", `Discovery collection cost: ${JSON.stringify(discovery.collection_cost)}`);
      if (discovery.run_error) appendText(scope, "p", discovery.run_error);
      for (const source of discovery.sources || []) link(scope, source.citation, `Search source · ${source.retrieved_at.slice(0, 10)} ↗`);
    }
    if (!discoveries.length) appendText(scope, "p", "No candidate discovery run is attached to this dataset. Verse reports and graphable counts do not establish completeness of the witness pool.");
    appendText(scope, "p", `${meta.counts.graphable_coordinates} graphable coordinates · ${meta.counts.mapping_gaps} mapping gaps. Witness/verse pairs: ${Object.entries(meta.counts.witness_verse_pairs).map(([key, value]) => `${value} ${key}`).join(" · ")}.`);
    appendText(scope, "p", `Filters: omitted ${meta.filters.include_omitted ? "included" : "excluded"}; bracketed ${meta.filters.include_bracketed ? "included" : "excluded"}. Filtered coordinates retain their horizontal positions.`);
    appendText(scope, "p", meta.inventory_scope);
    appendText(scope, "p", `Collection cost: ${JSON.stringify(meta.collection_cost)}`);
    appendText(scope, "p", `Axis inventory: ${data.coordinate_inventory.inventory_id}. ${data.coordinate_inventory.scope}`);
    link(scope, data.coordinate_inventory.source_citation);
    appendText(scope, "p", `Reported-coordinate source: ${meta.inventory_source_citation}`);
    appendText(scope, "p", `Mapping: ${meta.mapping_citation}`);
    for (const snapshot of data.sources) {
      const item = node("div", null, "source-record");
      appendText(item, "strong", `Response ${snapshot.source_response_id}`);
      const url = snapshot.canonical_url || snapshot.url;
      const params = new URLSearchParams(snapshot.params).toString();
      link(item, url + (params ? (url.includes("?") ? "&" : "?") + params : ""));
      appendText(item, "p", `Retrieved ${snapshot.retrieved_at}`);
      appendText(item, "code", snapshot.body_sha256); el("snapshots").append(item);
    }
    canvas.setAttribute("aria-valuemax", data.coordinates.length);
    for (const input of root.querySelectorAll('input[name="scenario"]')) on(input, "change", () => setScenario(input.value));
    on(el("source-details"), "toggle", () => {if (el("source-details").open) renderClaims(cachedCells[selected].ref);});
    on(el("previous"), "click", () => select(selected - 1, true, true));
    on(el("next"), "click", () => select(selected + 1, true, true));
    on(el("pin"), "click", () => select(selected, !pinned));
    on(el("zoom-in"), "click", () => setZoom(zoom * 2));
    on(el("zoom-out"), "click", () => setZoom(zoom / 2));
    on(el("reset"), "click", () => {el("book").value = ""; setZoom(1);});
    on(el("book"), "change", () => {
      const book = model.books.find(item => item.code === el("book").value);
      if (!book) {setZoom(1); return;}
      select(book.first, true);
      setZoom(data.coordinates.length / (book.end - book.first) * .9, (book.first + book.end) / 2);
    });
    on(el("jump-form"), "submit", event => {
      event.preventDefault(); const index = model.lookup(el("reference").value);
      el("error").hidden = index >= 0;
      if (index < 0) {el("error").textContent = "Reference not found. Use a book and verse, such as Gal 1:9 or John 3:16."; return;}
      select(index, true, true); setZoom(Math.max(zoom, 16));
    });
    on(scroll, "scroll", scheduleDraw);
    const pointerIndex = event => hitIndex(event.clientX - canvas.getBoundingClientRect().left, width,
      scroll.scrollLeft, totalWidth(), data.coordinates.length);
    let touch = null, moved = false;
    on(canvas, "pointerdown", event => {
      moved = false;
      if (event.pointerType === "touch") {touch = {x: event.clientX, offset: scroll.scrollLeft}; canvas.setPointerCapture(event.pointerId);}
    });
    on(canvas, "pointermove", event => {
      if (event.pointerType === "touch") {
        if (touch && Math.abs(event.clientX - touch.x) > 8 && zoom > 1) {moved = true; scroll.scrollLeft = touch.offset - (event.clientX - touch.x);}
      } else if (!pinned) select(pointerIndex(event), false);
    });
    on(canvas, "pointerup", () => {touch = null;});
    on(canvas, "pointercancel", () => {touch = null; moved = true;});
    on(canvas, "click", event => {if (!moved) select(pointerIndex(event), true);});
    on(canvas, "keydown", event => {
      const moves = {ArrowLeft: -1, ArrowRight: 1, PageUp: -20, PageDown: 20, Home: -selected, End: data.coordinates.length - 1 - selected};
      if (event.key in moves) {event.preventDefault(); select(selected + moves[event.key], true, true);}
      else if (event.key === "Escape") select(selected, false);
      else if (event.key === " " || event.key === "Enter") {event.preventDefault(); select(selected, !pinned);}
    });
    const observer = new view.ResizeObserver(resize); observer.observe(canvas);
    refreshCells(); renderSelection(); resize();
    return {
      setScenario,
      selectVerse(ref) {const index = model.lookup(ref); if (index < 0) return false; select(index, true, true); return true;},
      destroy() {abort.abort(); observer.disconnect(); view.cancelAnimationFrame(frame);}
    };
  }

  const api = {expandData, createDataStore, createModel, hitIndex, segments, mount};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else global.AttestationExplorer = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
