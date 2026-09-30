#!/usr/bin/env python3
"""Record or report independently checked physical absence, without network calls."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

from controlled_ntvmr import (OSIS, connect, physical_absence_report,
                              record_physical_absence_review)


FIELDS = {"format_version", "inventory_id", "osis_ref", "witness_id", "decision",
          "evidence_type", "source_locator", "reason", "citation", "reviewer"}


def validate_action(action):
    if not isinstance(action, dict) or set(action) != FIELDS or \
            type(action["format_version"]) is not int or action["format_version"] != 1:
        raise ValueError("Physical absence action has an unsupported shape")
    for key in FIELDS - {"format_version"}:
        if not isinstance(action[key], str) or not action[key].strip():
            raise ValueError(f"Physical absence action requires {key}")
    if not OSIS.fullmatch(action["osis_ref"]):
        raise ValueError("Physical absence action needs one OSIS verse")
    if action["decision"] not in ("absent", "uncertain", "withdrawn"):
        raise ValueError("Unknown physical absence decision")
    if action["evidence_type"] not in ("checked_image", "reviewed_transcription"):
        raise ValueError("Physical absence needs a checked image or reviewed transcription")
    return action


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--action", type=Path, help="One cited, append-only review JSON")
    mode.add_argument("--report", help="Inventory ID to inspect")
    parser.add_argument("--ref", help="Optional OSIS verse filter for --report")
    parser.add_argument("--dry-run", action="store_true", help="Validate action without opening the database")
    args = parser.parse_args(argv)
    if args.ref and not args.report:
        parser.error("--ref requires --report")
    if args.dry_run and not args.action:
        parser.error("--dry-run requires --action")
    if args.ref and not OSIS.fullmatch(args.ref):
        parser.error("--ref must be one OSIS verse")
    try:
        if args.action:
            action = validate_action(json.loads(args.action.read_text(encoding="utf-8")))
            if args.dry_run:
                print(json.dumps({"planned_absence_decision": action["decision"],
                                  "inventory_id": action["inventory_id"],
                                  "osis_ref": action["osis_ref"], "network_attempts": 0}))
                return 0
        with closing(connect(args.db)) as con:
            if args.action:
                review_id = record_physical_absence_review(
                    con, *(action[key] for key in (
                        "inventory_id", "osis_ref", "witness_id", "decision",
                        "evidence_type", "source_locator", "reason", "citation", "reviewer")))
                result = {"physical_absence_review_id": review_id, "network_attempts": 0}
            else:
                result = physical_absence_report(con, args.report, args.ref)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Physical absence review failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
