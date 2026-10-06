#!/usr/bin/env python3
"""
sync_ntvmr.py

Build a local, auditable SQLite dataset for Greek NT manuscript attestation.

Pipeline:
1. Creates the SQLite DB + tables if missing
2. Seeds verse using NTVMR's versification service (metadata/v11n/get)
3. For each verse, finds candidate Greek manuscripts via metadata/liste/search and stores the earliest attested manuscript (by dateMin, then dateMax)
4. Fetches detailed manuscript metadata (metadata/manuscript/get)
5. Builds verse coverage for those manuscripts using biblicalcontent/get (falls back to per-page mode if needed)

It's designed to be idempotent and update-friendly:
it caches API responses in api_cache, tracks fetched_at, and can be re-run anytime (use --refresh to force re-fetch).

Requires:
  pip install requests
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import xml.etree.ElementTree as ET

import requests


#API_BASE = "https://ntvmr.uni-muenster.de/community/vmr/api"
API_BASE = "http://192.168.0.119:8889/community/vmr/api"
# might also try ntvmr2.uni-muenster.de ??


# -----------------------------
# SQLite schema
# -----------------------------

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS verse (
  osis_ref TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS manuscript (
  doc_id INTEGER PRIMARY KEY,
  ga_num TEXT,
  date_min INTEGER,
  date_max INTEGER,
  raw_json TEXT,
  fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS manuscript_verse (
  doc_id INTEGER NOT NULL,
  osis_ref TEXT NOT NULL,
  source TEXT NOT NULL,
  page_id INTEGER,
  PRIMARY KEY (doc_id, osis_ref)
);

CREATE TABLE IF NOT EXISTS verse_earliest (
  osis_ref TEXT PRIMARY KEY,
  earliest_doc_id INTEGER,
  earliest_date_min INTEGER,
  earliest_date_max INTEGER,
  computed_at TEXT
);

-- Simple reproducible caching for API responses
CREATE TABLE IF NOT EXISTS api_cache (
  cache_key TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  params_json TEXT NOT NULL,
  status_code INTEGER NOT NULL,
  response_text TEXT NOT NULL,
  fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_manuscript_verse_doc ON manuscript_verse(doc_id);
CREATE INDEX IF NOT EXISTS idx_verse_earliest_doc ON verse_earliest(earliest_doc_id);
"""


# -----------------------------
# Helpers
# -----------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def stable_cache_key(url: str, params: Dict[str, Any]) -> str:
    # Sort params for stable key
    payload = {"url": url, "params": {k: params[k] for k in sorted(params.keys())}}
    return sha256_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))


def db_connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys=ON;")
    con.executescript(SCHEMA_SQL)
    return con


def db_scalar(con: sqlite3.Connection, sql: str, args: Sequence[Any] = ()) -> Any:
    cur = con.execute(sql, args)
    row = cur.fetchone()
    return row[0] if row else None


def db_exec(con: sqlite3.Connection, sql: str, args: Sequence[Any] = ()) -> None:
    con.execute(sql, args)


def db_many(con: sqlite3.Connection, sql: str, rows: Iterable[Sequence[Any]]) -> None:
    con.executemany(sql, rows)


def parse_int_or_none(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def pick_first(d: Dict[str, Any], keys: Sequence[str]) -> Any:
    for k in keys:
        if k in d and d[k] not in ("", None):
            return d[k]
    return None


def ensure_requests_ok(r: requests.Response, context: str) -> None:
    if not r.ok:
        raise RuntimeError(f"{context} failed: HTTP {r.status_code} {r.text[:300]}")


# -----------------------------
# API client with SQLite cache
# -----------------------------

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        # Chrome on Windows 10 style UA (harmless, widely accepted)
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    })
    return s


@dataclass
class ApiClient:
    con: sqlite3.Connection
    refresh: bool
    max_cache_age_days: int
    timeout_s: int
    sleep_s: float

    session: requests.Session = make_session()

    def get_text(self, url: str, params: Dict[str, Any]) -> Tuple[int, str]:
        key = stable_cache_key(url, params)
        cached = self._cache_get(key)
        if cached is not None:
            status_code, text, fetched_at = cached
            if not self.refresh and not self._is_cache_expired(fetched_at):
                return status_code, text

        r = self.session.get(url, params=params, timeout=self.timeout_s)
        status_code = r.status_code
        text = r.text
        self._cache_put(key, url, params, status_code, text)
        if self.sleep_s > 0:
            time.sleep(self.sleep_s)
        return status_code, text

    def get_json(self, url: str, params: Dict[str, Any]) -> Any:
        status, text = self.get_text(url, params)
        if status < 200 or status >= 300:
            raise RuntimeError(f"GET {url} failed: HTTP {status} {text[:300]}")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Expected JSON from {url}, got parse error: {e} (first 300 chars: {text[:300]!r})")

    def _cache_get(self, cache_key: str) -> Optional[Tuple[int, str, str]]:
        cur = self.con.execute(
            "SELECT status_code, response_text, fetched_at FROM api_cache WHERE cache_key=?",
            (cache_key,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return int(row[0]), str(row[1]), str(row[2])

    def _cache_put(self, cache_key: str, url: str, params: Dict[str, Any], status_code: int, response_text: str) -> None:
        self.con.execute(
            """
            INSERT INTO api_cache(cache_key, url, params_json, status_code, response_text, fetched_at)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(cache_key) DO UPDATE SET
              url=excluded.url,
              params_json=excluded.params_json,
              status_code=excluded.status_code,
              response_text=excluded.response_text,
              fetched_at=excluded.fetched_at
            """,
            (
                cache_key,
                url,
                json.dumps({k: params[k] for k in sorted(params.keys())}, ensure_ascii=True),
                int(status_code),
                response_text,
                utc_now_iso(),
            ),
        )

    def _is_cache_expired(self, fetched_at_iso: str) -> bool:
        try:
            fetched_dt = datetime.fromisoformat(fetched_at_iso.replace("Z", "+00:00"))
        except Exception:
            return True
        max_age = timedelta(days=self.max_cache_age_days)
        return datetime.now(timezone.utc) - fetched_dt > max_age


# -----------------------------
# Step A: Seed verses via v11n/get
# -----------------------------
def _strip_xml_namespaces(root: ET.Element) -> ET.Element:
    # In-place namespace stripping: "{ns}tag" -> "tag"
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root

def seed_verses_from_v11n(api: ApiClient, con: sqlite3.Connection, v11nid: str, subset: str) -> int:
    """
    XML-only verse seeding from NTVMR versification endpoint.

    Works with XML where <chapter> is self-closing and stores osisID/verseMax as attributes:
    <chapter osisID="John.1" verseMax="51"/>

    Also tolerates the alternative representation where osisID/verseMax are child elements.
    """
    url = f"{API_BASE}/metadata/v11n/get/"
    params = {
        "v11nid": v11nid,
        "detail": "chapter",
        "subset": subset,  # e.g. "John" or "NT"
        # No "format" on purpose; the endpoint returns XML by default.
    }

    status, text = api.get_text(url, params)
    if status < 200 or status >= 300:
        raise RuntimeError(f"v11n/get failed: HTTP {status} {text[:300]}")

    body = text.lstrip()
    if not body.startswith("<"):
        raise RuntimeError(f"Expected XML from v11n/get, got non-XML (first 200 chars): {body[:200]!r}")

    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise RuntimeError(f"v11n/get returned XML but could not parse it: {e}")

    _strip_xml_namespaces(root)

    to_insert: List[Tuple[str]] = []

    for ch in root.findall(".//chapter"):
        # Preferred: attributes on a self-closing <chapter ... />
        osis_ch = (ch.attrib.get("osisID") or "").strip()
        verse_max_raw = (ch.attrib.get("verseMax") or "").strip()

        # Tolerate alt form: <chapter><osisID>John.1</osisID><verseMax>51</verseMax></chapter>
        if not osis_ch:
            osis_id_el = ch.find("osisID")
            osis_ch = ((osis_id_el.text if osis_id_el is not None else "") or "").strip()
        if not verse_max_raw:
            verse_max_el = ch.find("verseMax")
            verse_max_raw = ((verse_max_el.text if verse_max_el is not None else "") or "").strip()

        verse_max = parse_int_or_none(verse_max_raw)
        if not osis_ch or verse_max is None or verse_max <= 0:
            continue

        parts = osis_ch.split(".")
        if len(parts) != 2:
            continue
        book = parts[0]
        chap = parse_int_or_none(parts[1])
        if chap is None:
            continue

        for v in range(1, verse_max + 1):
            to_insert.append((f"{book}.{chap}.{v}",))

    db_many(con, "INSERT OR IGNORE INTO verse(osis_ref) VALUES(?)", to_insert)
    con.commit()
    return len(to_insert)



# -----------------------------
# Step B: Verse -> earliest manuscript (liste/search)
# -----------------------------

def extract_docs_from_liste_search(payload: Any) -> List[Dict[str, Any]]:
    """Normalize liste/search responses into a list of document/manuscript dicts.

    Handles the shape:
      {"status":"success","data":{"manuscripts":{"manuscript":[ ... ]}}}

    Also keeps older/alternate shapes working when possible.
    """
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    if not isinstance(payload, dict):
        return []

    # Newer/common shape
    data = payload.get("data")
    if isinstance(data, dict):
        mss = data.get("manuscripts")
        if isinstance(mss, dict):
            ms = mss.get("manuscript")
            if isinstance(ms, list):
                return [x for x in ms if isinstance(x, dict)]
            if isinstance(ms, dict):
                return [ms]

    # Fallback keys we saw in other versions
    for k in ("documents", "docs", "results", "rows"):
        v = payload.get(k)
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]

    return []


def choose_earliest_doc(docs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not docs:
        return None

    def get_date_min(d: Dict[str, Any]) -> int:
        # NTVMR liste/search commonly uses origEarly/origLate
        v = pick_first(d, ["origEarly", "dateMin", "date_min", "minDate", "earliestDate"])
        iv = parse_int_or_none(v)
        return iv if iv is not None else 10**9

    def get_date_max(d: Dict[str, Any]) -> int:
        v = pick_first(d, ["origLate", "dateMax", "date_max", "maxDate", "latestDate"])
        iv = parse_int_or_none(v)
        return iv if iv is not None else 10**9

    def get_doc_id(d: Dict[str, Any]) -> int:
        v = pick_first(d, ["docID", "docId", "doc_id", "id"])
        iv = parse_int_or_none(v)
        return iv if iv is not None else 10**9

    # Filter out undated manuscripts where both bounds are 0
    filtered: List[Dict[str, Any]] = []
    for d in docs:
        dmin = get_date_min(d)
        dmax = get_date_max(d)
        if dmin == 0 and dmax == 0:
            continue
        filtered.append(d)

    if not filtered:
        return None

    # Deterministic ordering: earliest lower bound, then earliest upper bound, then stable docID
    return sorted(filtered, key=lambda d: (get_date_min(d), get_date_max(d), get_doc_id(d)))[0]


def upsert_manuscript_stub(con: sqlite3.Connection, doc: Dict[str, Any]) -> int:
    doc_id = parse_int_or_none(pick_first(doc, ["docID", "docId", "doc_id", "id"]))
    if doc_id is None:
        raise RuntimeError(f"Could not find docID in document: {list(doc.keys())}")

    ga_num = pick_first(doc, ["gaNum", "ga_num", "primaryName", "name"])

    # Match liste/search field names in your payload
    date_min = parse_int_or_none(pick_first(doc, ["origEarly", "dateMin", "date_min", "minDate"]))
    date_max = parse_int_or_none(pick_first(doc, ["origLate", "dateMax", "date_max", "maxDate"]))

    con.execute(
        """
        INSERT INTO manuscript(doc_id, ga_num, date_min, date_max, raw_json, fetched_at)
        VALUES(?,?,?,?,COALESCE((SELECT raw_json FROM manuscript WHERE doc_id=?), NULL), COALESCE((SELECT fetched_at FROM manuscript WHERE doc_id=?), NULL))
        ON CONFLICT(doc_id) DO UPDATE SET
          ga_num=COALESCE(excluded.ga_num, manuscript.ga_num),
          date_min=COALESCE(excluded.date_min, manuscript.date_min),
          date_max=COALESCE(excluded.date_max, manuscript.date_max)
        """,
        (doc_id, ga_num, date_min, date_max, doc_id, doc_id),
    )
    return doc_id


def compute_earliest_for_verse(api: ApiClient, con: sqlite3.Connection, osis_ref: str) -> Optional[Tuple[int, Optional[int], Optional[int]]]:
    url = f"{API_BASE}/metadata/liste/search/"
    params = {
        "indexContent": osis_ref,
        "lang": "gr",
        "detail": "document",
        "format": "json",
    }
    payload = api.get_json(url, params)
    docs = extract_docs_from_liste_search(payload)
    earliest = choose_earliest_doc(docs)
    if earliest is None:
        return None

    doc_id = upsert_manuscript_stub(con, earliest)
    date_min = parse_int_or_none(pick_first(earliest, ["origEarly", "dateMin", "date_min", "minDate"]))
    date_max = parse_int_or_none(pick_first(earliest, ["origLate", "dateMax", "date_max", "maxDate"]))

    con.execute(
        """
        INSERT INTO verse_earliest(osis_ref, earliest_doc_id, earliest_date_min, earliest_date_max, computed_at)
        VALUES(?,?,?,?,?)
        ON CONFLICT(osis_ref) DO UPDATE SET
          earliest_doc_id=excluded.earliest_doc_id,
          earliest_date_min=excluded.earliest_date_min,
          earliest_date_max=excluded.earliest_date_max,
          computed_at=excluded.computed_at
        """,
        (osis_ref, doc_id, date_min, date_max, utc_now_iso()),
    )
    return doc_id, date_min, date_max


# -----------------------------
# Step C: Manuscript metadata + coverage
# -----------------------------

def fetch_and_store_manuscript_metadata(api: ApiClient, con: sqlite3.Connection, doc_id: int, detail: int = 10) -> None:
    url = f"{API_BASE}/metadata/manuscript/get/"
    params = {"docID": str(doc_id), "detail": str(detail), "format": "json"}
    payload = api.get_json(url, params)
    con.execute(
        """
        UPDATE manuscript
        SET raw_json=?, fetched_at=?
        WHERE doc_id=?
        """,
        (json.dumps(payload, ensure_ascii=True), utc_now_iso(), doc_id),
    )


def extract_osis_refs_from_biblicalcontent(payload: Any) -> List[Tuple[str, Optional[int]]]:
    """
    Returns list of (osis_ref, page_id) tuples when possible.
    detail=long is supposed to "break them up into individual entries" so we try to grab direct refs.
    """
    out: List[Tuple[str, Optional[int]]] = []

    def visit(node: Any, page_id: Optional[int]) -> None:
        if isinstance(node, dict):
            # Some likely keys
            maybe_ref = pick_first(node, ["osisRef", "osis_ref", "ref", "key", "verse", "biblicalContent"])
            if isinstance(maybe_ref, str) and "." in maybe_ref and maybe_ref.count(".") >= 2:
                out.append((maybe_ref.strip(), page_id))

            # Detect page id if present
            pid = parse_int_or_none(pick_first(node, ["pageID", "pageId", "page_id"]))
            if pid is not None:
                page_id = pid

            for v in node.values():
                visit(v, page_id)
        elif isinstance(node, list):
            for item in node:
                visit(item, page_id)

    visit(payload, None)
    # Dedup while preserving first page_id seen
    seen: Dict[str, Optional[int]] = {}
    for ref, pid in out:
        if ref not in seen:
            seen[ref] = pid
    return [(r, seen[r]) for r in seen]


def get_page_ids_for_doc(api: ApiClient, doc_id: int) -> List[int]:
    # Ask liste/search for page-level rows and pluck pageIDs.
    url = f"{API_BASE}/metadata/liste/search/"
    params = {"docID": str(doc_id), "detail": "page", "format": "json"}
    payload = api.get_json(url, params)
    rows = extract_docs_from_liste_search(payload)
    page_ids: List[int] = []
    for r in rows:
        pid = parse_int_or_none(pick_first(r, ["pageID", "pageId", "page_id"]))
        if pid is not None:
            page_ids.append(pid)
    return sorted(set(page_ids))


def fetch_and_store_coverage(api: ApiClient, con: sqlite3.Connection, doc_id: int, restrict_to_subset_book: Optional[str]) -> int:
    """
    Attempts doc-level biblicalcontent/get first.
    If that yields no OSIS refs, falls back to per-page calls.
    """
    url = f"{API_BASE}/biblicalcontent/get/"
    params = {"docID": str(doc_id), "detail": "long", "format": "json"}

    inserted = 0
    payload = api.get_json(url, params)
    refs = extract_osis_refs_from_biblicalcontent(payload)

    if not refs:
        # Fallback: iterate pages
        page_ids = get_page_ids_for_doc(api, doc_id)
        for pid in page_ids:
            payload_p = api.get_json(url, {"docID": str(doc_id), "pageID": str(pid), "detail": "long", "format": "json"})
            refs.extend(extract_osis_refs_from_biblicalcontent(payload_p))

    # Optional restriction to the subset book (e.g., "John") to keep DB smaller in early runs
    if restrict_to_subset_book:
        prefix = restrict_to_subset_book + "."
        refs = [(r, pid) for (r, pid) in refs if r.startswith(prefix)]

    rows = []
    for ref, pid in refs:
        rows.append((doc_id, ref, "biblicalcontent/get", pid))

    if rows:
        db_many(
            con,
            "INSERT OR IGNORE INTO manuscript_verse(doc_id, osis_ref, source, page_id) VALUES(?,?,?,?)",
            rows,
        )
        inserted = con.total_changes

    return inserted


# -----------------------------
# Main
# -----------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Sync Greek NT verse attestation data from NTVMR into SQLite.")
    ap.add_argument("--db", default="data/.cache/local/ntvmr.sqlite", help="Legacy SQLite cache; not an input to the explorer")
    ap.add_argument("--subset", default="John", help='Versification subset for seeding verses (e.g., "John" or "NT")')
    ap.add_argument("--v11n", default="KJV", help='Versification ID (default: "KJV")')
    ap.add_argument("--max-verses", type=int, default=0, help="Process only first N verses (0 = all seeded)")
    ap.add_argument("--refresh", action="store_true", help="Force re-fetch API responses (ignore cache)")
    ap.add_argument("--max-cache-age-days", type=int, default=30, help="Cache TTL in days (default: 30)")
    ap.add_argument("--timeout", type=int, default=60, help="HTTP timeout seconds (default: 60)")
    ap.add_argument("--sleep", type=float, default=1, help="Sleep seconds between requests (default: 1)")
    ap.add_argument("--reseed", action="store_true", help="Reseed verse table (keeps existing rows, but re-pulls versification)")
    ap.add_argument("--recompute", action="store_true", help="Recompute earliest for verses even if already present")
    ap.add_argument("--coverage", action="store_true", help="Also fetch/store manuscript verse coverage for earliest manuscripts")
    args = ap.parse_args()

    con = db_connect(args.db)
    api = ApiClient(
        con=con,
        refresh=bool(args.refresh),
        max_cache_age_days=int(args.max_cache_age_days),
        timeout_s=int(args.timeout),
        sleep_s=float(args.sleep),
    )

    # Seed verses if needed
    verse_count = db_scalar(con, "SELECT COUNT(*) FROM verse")
    if verse_count == 0 or args.reseed:
        n = seed_verses_from_v11n(api, con, args.v11n, args.subset)
        print(f"Seeded {n} verses into verse table from subset={args.subset!r} v11n={args.v11n!r}")

    # Load verse list to process
    verses: List[str] = [r[0] for r in con.execute("SELECT osis_ref FROM verse ORDER BY osis_ref").fetchall()]
    if args.max_verses and args.max_verses > 0:
        verses = verses[: args.max_verses]

    print(f"Processing {len(verses)} verses...")

    processed = 0
    for osis_ref in verses:
        if not args.recompute:
            exists = db_scalar(con, "SELECT 1 FROM verse_earliest WHERE osis_ref=?", (osis_ref,))
            if exists:
                processed += 1
                continue

        try:
            result = compute_earliest_for_verse(api, con, osis_ref)
            con.commit()
            processed += 1

            if result is None:
                print(f"[{processed}/{len(verses)}] {osis_ref}: no Greek manuscripts returned (or not indexed)")
                continue

            doc_id, dmin, dmax = result
            print(f"[{processed}/{len(verses)}] {osis_ref}: earliest docID={doc_id} date={dmin}-{dmax}")

            # Fetch detailed metadata if missing or refresh requested
            if args.refresh or db_scalar(con, "SELECT raw_json FROM manuscript WHERE doc_id=?", (doc_id,)) in (None, ""):
                fetch_and_store_manuscript_metadata(api, con, doc_id, detail=10)
                con.commit()

            if args.coverage:
                # Restrict coverage to subset book if subset is a single book (not OT/NT)
                restrict_book = args.subset if args.subset not in ("OT", "NT") and "." not in args.subset else None
                inserted = fetch_and_store_coverage(api, con, doc_id, restrict_to_subset_book=restrict_book)
                con.commit()
                if inserted:
                    print(f"  coverage: inserted {inserted} manuscript_verse rows for docID={doc_id}")

        except Exception as e:
            con.rollback()
            print(f"ERROR on {osis_ref}: {e}", file=sys.stderr)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit("Legacy collector is archived for review only; use sync_ntvmr.py")
