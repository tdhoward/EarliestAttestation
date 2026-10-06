#!/usr/bin/env python3
"""Render a bounded graph-input export as a self-contained prototype HTML file."""

from __future__ import annotations

import argparse
from html import escape
from itertools import product
import json
from pathlib import Path
import re
from urllib.parse import urlencode


COLORS = ("#dcebe7", "#a9d7c6", "#72b99f", "#388f76", "#146553")
URL = re.compile(r"https?://[^\s;,]+")


def source(text):
    if not text:
        return "Source unavailable"
    match = URL.search(text)
    if not match:
        return escape(text)
    url = match.group().rstrip(".)")
    return (escape(text[:match.start()]) +
            f'<a href="{escape(url, quote=True)}">{escape(url)}</a>' +
            escape(text[match.start() + len(url):]))


def evidence_detail(verse):
    """Show current source reviews even when no witness can be dated."""
    evidence = verse.get("evidence")
    if evidence is None:
        return '<p>Coverage review details unavailable in this older export.</p>'
    coverage = evidence["coverage_reviews"]
    absences = evidence["physical_absence_reviews"]
    if not coverage and not absences:
        return '<p>No physical coverage review recorded for this coordinate.</p>'
    parts = ['<p><strong>Physical evidence:</strong> '
             f'{len(evidence["positive_witness_ids"])} reviewed positive witnesses; '
             f'{len(evidence["absent_witness_ids"])} reviewed absent witnesses; '
             f'{len(evidence["conflicting_witness_ids"])} conflicting witnesses. '
             'Counts describe the reviewed witnesses only.</p>']
    if evidence["conflicting_witness_ids"]:
        parts.append('<p class="notice">Conflicting survival and absence reviews for '
                     + escape(', '.join(evidence["conflicting_witness_ids"])) +
                     '; dated results are held pending review.</p>')
    for review in absences:
        label = {"absent": "Reviewed physical absence",
                 "uncertain": "Physical absence uncertain",
                 "withdrawn": "Physical absence review withdrawn"}[review["decision"]]
        parts.append(f'<p><strong>{label}:</strong> {escape(review["witness_id"])}. '
                     f'{escape(review["source_locator"])}. '
                     f'{escape(review["reason"])} '
                     f'Evidence: {escape(review["evidence_type"])}. '
                     f'Reviewed by {escape(review["reviewer"])} '
                     f'({escape(review["reviewed_at"])}); '
                     f'{source(review["citation"])}</p>')
    if coverage:
        parts.append('<details><summary>Coverage source reviews '
                     f'({len(coverage)})</summary>')
        for review in coverage:
            status = escape(review["status"])
            if review["review_needed"]:
                status += '; renewed review needed'
            parts.append(f'<p><strong>{escape(review["witness_id"])}: {status}</strong>. '
                         f'Document {review["doc_id"]}, page {review["page_id"]}, '
                         f'{escape(review["ntvmr_ref"])}. '
                         f'{escape(review["reason"])} '
                         f'Evidence: {escape(review["evidence_type"])}. '
                         f'Reviewed by {escape(review["reviewer"])} '
                         f'({escape(review["reviewed_at"])}); '
                         f'{source(review["citation"])}</p>')
        parts.append('</details>')
    return ''.join(parts)


def cases_for(graph):
    if graph.get("format_version") not in (2, 3) or graph.get("kind") != "graph_input":
        raise ValueError("Expected a version 2 or 3 graph-input export")
    assessment_key = "witness_id" if graph["format_version"] == 3 else "unit_id"
    verses = graph["verses"]
    if not verses or len(verses) > 20 or graph["counts"]["verse_count"] != len(verses):
        raise ValueError("Render a bounded graph input of 1–20 verses")
    units = {}
    for verse in verses:
        alternatives = verse.get("dating_alternatives")
        if alternatives and alternatives["state"] == "complete":
            for combination in alternatives["combinations"]:
                for assessment in combination["assessments"]:
                    units.setdefault(assessment[assessment_key], set()).add(
                        assessment["assessment_id"])
    count = 1
    for values in units.values():
        count *= len(values)
    if count > 256:
        return [], count
    cases = []
    for selected in product(*(sorted(units[unit]) for unit in sorted(units))):
        selection = dict(zip(sorted(units), selected))
        rows = []
        for verse in verses:
            alternatives = verse.get("dating_alternatives")
            combination = None
            if alternatives and alternatives["state"] == "complete":
                combination = next((item for item in alternatives["combinations"]
                    if all(selection.get(a[assessment_key]) == a["assessment_id"]
                           for a in item["assessments"])), None)
            scenarios = (combination["scenarios"] if combination else
                         verse.get("scenarios") if alternatives is None and
                         verse["ranking_state"] in ("success", "empty") else None)
            rows.append((verse, combination, scenarios))
        cases.append((selection, rows))
    return cases, count


def chart(rows, scenario, minimum, maximum, pattern_id):
    top, height, left, width = 42, 360, 68, 82
    bottom = top + height
    total_width = left + len(rows) * width + 12
    y = lambda year: top + (maximum - year) * height / (maximum - minimum)
    out = [f'<svg viewBox="0 0 {total_width} 452" role="img" '
           f'aria-label="{escape(scenario.title())} witness counts by CE year">',
           f'<defs><pattern id="{pattern_id}" width="8" height="8" patternUnits="userSpaceOnUse">'
           '<rect width="8" height="8" fill="#eceff2"/>'
           '<path d="M0 8L8 0" stroke="#c5ccd2"/></pattern></defs>']
    for tick in range(5):
        year = minimum + (maximum - minimum) * tick / 4
        py = y(year)
        out.append(f'<line x1="{left}" y1="{py:.1f}" x2="{total_width-12}" '
                   'y2="{:.1f}" stroke="#dae0e3"/>'.format(py))
        out.append(f'<text x="{left-8}" y="{py+4:.1f}" text-anchor="end" '
                   f'font-size="12">{year:.0f}</text>')
    out.append('<text x="6" y="20" font-size="12">CE year ↑ newer</text>')
    for index, (verse, _, scenarios) in enumerate(rows):
        x = left + index * width + 3
        entries = scenarios[scenario] if scenarios is not None else None
        if entries is None or not entries:
            out.append(f'<rect x="{x}" y="{top}" width="76" height="{height}" '
                       f'fill="url(#{pattern_id})"/>')
        else:
            by_year = {}
            for entry in entries:
                by_year[entry["event_year"]] = by_year.get(entry["event_year"], 0) + 1
            previous = minimum
            count = 0
            for year, added in sorted(by_year.items()):
                if count and year > previous:
                    out.append(f'<rect x="{x}" y="{y(year):.1f}" width="76" '
                               f'height="{y(previous)-y(year):.1f}" '
                               f'fill="{COLORS[min(count,5)-1]}"/>')
                previous = year
                count += added
            out.append(f'<rect x="{x}" y="{top}" width="76" '
                       f'height="{y(previous)-top:.1f}" '
                       f'fill="{COLORS[min(count,5)-1]}"/>')
        out.append(f'<rect x="{x}" y="{top}" width="76" height="{height}" '
                   'fill="none" stroke="#9ba8ad"/>')
        label = f'{verse["chapter"]}:{verse["verse"]}'
        out.append(f'<text x="{x+38}" y="{bottom+20}" text-anchor="middle" '
                   f'font-size="12">{escape(label)}</text>')
        if verse["editorial_status"] != "main":
            out.append(f'<text x="{x+38}" y="{bottom+34}" text-anchor="middle" '
                       f'font-size="10">{escape(verse["editorial_status"])}</text>')
    out.append('</svg>')
    return "".join(out)


def render(graph):
    if graph.get("format_version") == 3:
        return render_reports(graph)
    cases, count = cases_for(graph)
    verses = graph["verses"]
    years = [entry["event_year"] for _, rows in cases for _, _, scenarios in rows
             if scenarios for side in ("optimistic", "pessimistic")
             for entry in scenarios[side]]
    minimum, maximum = (min(years) - 10, max(years) + 10) if years else (0, 1)
    if minimum == maximum:
        maximum += 1
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>Surviving Greek verse evidence — prototype</title>',
             '<style>body{font:16px/1.45 system-ui,sans-serif;max-width:1100px;margin:auto;padding:2rem;color:#172b30}'
             'h1,h2{line-height:1.2} .notice{background:#fff1d6;padding:1rem;border-left:5px solid #ad6821}'
             '.charts{display:grid;grid-template-columns:1fr 1fr;gap:1rem;overflow:auto}'
             'svg{min-width:500px;width:100%}table{border-collapse:collapse;width:100%}'
             'th,td{border:1px solid #cad3d6;padding:.45rem;vertical-align:top;text-align:left}'
             'th{background:#eaf0ef}details{margin:1rem 0}a{overflow-wrap:anywhere}'
             '.legend span{display:inline-block;padding:.3rem .5rem;margin:.15rem}</style><body>',
             '<h1>Surviving Greek verse evidence</h1>',
             '<p class="notice"><strong>Prototype: incomplete discovery and validation.</strong> '
             'Dates show the earliest among reviewed, dated witnesses in this dataset. '
             'They do not date composition or establish exact NA28 wording.</p>',
             f'<p><strong>Inventory:</strong> {escape(graph["inventory_id"])} · '
             f'{escape(graph["inventory_scope"])}<br>'
             f'<strong>Dating policy:</strong> {escape(graph["dating_policy_id"])} · '
             f'<strong>Inventory review:</strong> {escape(graph["inventory_reviewer"])} · '
             f'<strong>Included verses:</strong> {len(verses)} · '
             f'<strong>Discovered documents:</strong> '
             f'{graph["counts"].get("discovered_document_count", 0)} (candidates only) · '
             f'<strong>Include omitted:</strong> {str(graph["filters"]["include_omitted"]).lower()} · '
             f'<strong>Include bracketed:</strong> {str(graph["filters"]["include_bracketed"]).lower()}</p>',
             '<p class="legend">Witness count: ' + ''.join(
                 f'<span style="background:{color}">{i}</span>' for i, color in
                 enumerate(COLORS, 1)) +
             ' <span style="background:#eceff2">Unknown or no dated witness</span></p>']
    if not cases:
        parts.append(f'<p class="notice">{count} global dating combinations exceed the '
                     '256-case display limit. No combination is selected for a chart. '
                     'All per-verse states remain listed below.</p>')
    for case_number, (selection, rows) in enumerate(cases, 1):
        parts.append(f'<section><h2>Conditional dating combination {case_number} of '
                     f'{len(cases)}</h2><p>Ordered by assessment ID; no combination is '
                     'preferred. Selected assessment IDs: '
                     f'{escape(json.dumps(selection, sort_keys=True))}.</p>')
        parts.append('<div class="charts">')
        for side in ("optimistic", "pessimistic"):
            parts.append(f'<div><h3>{side.title()} endpoint</h3>' +
                         chart(rows, side, minimum, maximum,
                               f'unknown-{case_number}-{side}') + '</div>')
        parts.append('</div></section>')
    parts.append('<h2>Evidence and unresolved work</h2><table><thead><tr><th>Verse</th>'
                 '<th>State</th><th>Physical evidence, dating inputs and ranked witnesses</th></tr></thead><tbody>')
    for verse in verses:
        alt = verse.get("dating_alternatives")
        state = alt["state"] if alt else verse["ranking_state"]
        detail = [evidence_detail(verse)]
        if verse.get("discovery_candidates"):
            detail.append('<p><strong>Named search candidates:</strong> ')
            detail.append('; '.join(
                f'{escape(candidate["query_ga_num"])} (document '
                f'{candidate["doc_id"]}, '
                f'{escape(candidate.get("review_decision", "unreviewed"))}'
                + (f', witness {escape(candidate["witness_id"])}'
                   if candidate.get("witness_id") else '') + ', '
                f'{escape(candidate["search_state"])} search; '
                f'<a href="{escape(candidate["source_url"], quote=True)}">'
                f'source response {candidate["source_response_id"]}</a>)'
                for candidate in verse["discovery_candidates"]))
            detail.append('. Search evidence alone does not establish physical verse coverage.</p>')
        if alt:
            detail.append(f'{alt["combination_count"]} possible combinations; '
                          f'{alt["eligible_witness_count"]} eligible physical witnesses. '
                          f'Excluded reviews: {escape(json.dumps(alt["excluded_reviews"]))}.')
            for assessment in alt.get("unrankable_assessments", []):
                detail.append(f'<p>Unrankable assessment {assessment["assessment_id"]} '
                              f'({escape(assessment["status"])}): '
                              f'{escape(assessment["original_notation"])}. '
                              f'Recorded by {escape(assessment["reviewer"])}. '
                              f'{source(assessment["citation"])}</p>')
            for number, combination in enumerate(alt["combinations"], 1):
                detail.append(f'<details><summary>Combination {number}: '
                              'assessment IDs ' + escape(", ".join(
                                  str(a["assessment_id"]) for a in
                                  combination["assessments"])) + '</summary>')
                for assessment in combination["assessments"]:
                    detail.append(f'<p>{escape(assessment["unit_id"])}: '
                                  f'{assessment["date_min"]}–{assessment["date_max"]} CE; '
                                  f'{escape(assessment["original_notation"])}. '
                                  f'Recorded by {escape(assessment["reviewer"])}. '
                                  f'{source(assessment["citation"])}</p>')
                for side in ("optimistic", "pessimistic"):
                    detail.append(f'<p><strong>{side.title()}:</strong> ')
                    entries = combination["scenarios"][side]
                    detail.append('; '.join(
                        f'{entry["rank"]}. {escape(entry["witness_id"])} '
                        f'({entry["event_year"]} CE; interval '
                        f'{entry["date_min"]}–{entry["date_max"]} CE; '
                        f'{escape(entry["coverage_status"])}) '
                        f'coverage reviewed by {escape(entry["coverage_reviewer"])}; '
                        f'coverage: {source(entry["coverage_citation"])}'
                        for entry in entries) or 'No dated witness')
                    detail.append('</p>')
                detail.append('</details>')
        elif verse.get("scenarios"):
            for side in ("optimistic", "pessimistic"):
                entries = verse["scenarios"][side]
                if entries:
                    detail.append(f'<p>{side.title()}: ' + '; '.join(
                        f'{entry["rank"]}. {escape(entry["witness_id"])} '
                        f'({entry["event_year"]} CE; interval '
                        f'{entry["date_min"]}–{entry["date_max"]} CE; '
                        f'{escape(entry["original_notation"])}; '
                        f'{escape(entry["coverage_status"])}) '
                        f'coverage: {source(entry["coverage_citation"])}; '
                        f'date: {source(entry["date_citation"])}'
                        for entry in entries) + '</p>')
        if verse.get("mapping_note"):
            detail.append('<p>Mapping: ' + escape(verse["mapping_note"]) + '</p>')
        parts.append(f'<tr><th>{escape(verse["osis_ref"])}</th><td>'
                     f'{escape(verse["editorial_status"])}; {escape(state)}</td><td>' +
                     ''.join(detail) + '</td></tr>')
    parts.append('</tbody></table><p>Inventory source: ' +
                 source(graph["inventory_source_citation"]) + '</p></body></html>')
    return "\n".join(parts)


def render_reports(graph):
    """Display attributable reports, including deferred disputes and missing data."""
    if graph.get("evidence_policy") != "scholarly_reports_only":
        raise ValueError("Version 3 requires the scholarly-report evidence policy")
    cases, count = cases_for(graph)
    years = [e["event_year"] for _, rows in cases for _, _, scenarios in rows
             if scenarios for entries in scenarios.values() for e in entries]
    minimum, maximum = (min(years)-10, max(years)+10) if years else (0, 1)
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>Earliest reported Greek NT witnesses</title>',
             '<style>body{font:16px/1.45 system-ui,sans-serif;max-width:1200px;margin:auto;padding:2rem;color:#172b30}'
             'h1,h2{line-height:1.2}.notice{background:#fff1d6;padding:1rem;border-left:5px solid #ad6821}'
             '.charts{display:grid;grid-template-columns:1fr 1fr;gap:1rem;overflow:auto}'
             'svg{min-width:500px;width:100%}table{border-collapse:collapse;width:100%}'
             'th,td{border:1px solid #cad3d6;padding:.45rem;vertical-align:top;text-align:left}'
             'th{background:#eaf0ef}details{margin:.5rem 0}a,code{overflow-wrap:anywhere}'
             '.legend span{display:inline-block;padding:.3rem .5rem;margin:.15rem}'
             '.contested{background:#ffe4dc}.unknown{background:#eceff2}</style><body>',
             '<h1>Earliest reported Greek NT witnesses</h1>',
             '<p class="notice">Bounded scholarly-source chart. Dates show the earliest '
             'witnesses reported in the collected sources and declared scope. Discovery is incomplete. '
             'Any reported portion counts once. Contested cases are deferred and excluded from '
             'presence counts. Missing entries remain unknown.</p>',
             '<p><strong>Collected scope:</strong> ' + escape(graph["collection_scope"]) + '</p>',
             f'<p>{graph["counts"]["document_count"]} documents; '
             f'{graph["counts"]["witness_count"]} distinct witnesses; '
             f'{graph["counts"]["verse_count"]} coordinates; '
             f'{graph["counts"]["graphable_coordinates"]} graphable; '
             f'{graph["counts"]["mapping_gaps"]} mapping gaps. '
             'Witness/verse states: ' + escape(json.dumps(graph["counts"]["witness_verse_pairs"], sort_keys=True)) + '</p>',
             '<p>Collection cost: ' + escape(json.dumps(graph["collection_cost"], sort_keys=True)) + '</p>',
             '<p>Filters: include omitted ' + str(graph["filters"]["include_omitted"]).lower() +
             '; include bracketed ' + str(graph["filters"]["include_bracketed"]).lower() + '.</p>',
             '<p class="legend">Witness count: ' + ''.join(
                 f'<span style="background:{color}">{i}</span>' for i, color in enumerate(COLORS, 1)) +
             ' <span style="background:#eceff2">No dated presence event</span></p>']
    if not cases:
        parts.append(f'<p class="notice">{count} global date combinations exceed the 256-case display limit. '
                     'No date alternative is selected; reports remain visible below.</p>')
    for verse in graph["verses"]:
        alt = verse["dating_alternatives"]
        if alt["state"] == "too_many_combinations":
            parts.append(f'<p class="notice">{escape(verse["osis_ref"])}: '
                         f'{alt["combination_count"]} complete date combinations exceed the '
                         f'{alt["max_combinations"]}-case limit. No alternative is selected for this verse.</p>')
    for number, (selection, rows) in enumerate(cases, 1):
        parts.append(f'<section><h2>Date combination {number} of {len(cases)}</h2>'
                     '<p>Complete reported intervals are equally valid alternatives; no combination is preferred. '
                     'Selected source assessment IDs: ' + escape(json.dumps(selection, sort_keys=True)) + '</p><div class="charts">')
        for side in ("optimistic", "pessimistic"):
            parts.append(f'<div><h3>{side.title()} endpoint</h3>' + chart(
                rows, side, minimum, maximum, f'reports-{number}-{side}') + '</div>')
        parts.append('</div></section>')
    parts.append('<h2>Endpoint rankings</h2><table><thead><tr><th>Verse</th><th>Combination</th>'
                 '<th>Optimistic</th><th>Pessimistic</th></tr></thead><tbody>')
    for verse in graph["verses"]:
        for number, combo in enumerate(verse["dating_alternatives"]["combinations"], 1):
            parts.append(f'<tr><th>{escape(verse["osis_ref"])}</th><td>{number}</td>')
            for side in ("optimistic", "pessimistic"):
                parts.append('<td>' + '<br>'.join(
                    f'{entry["rank"]}. {escape(entry["witness_id"])}: {entry["event_year"]} CE '
                    f'(reported interval {entry["date_min"]}–{entry["date_max"]} CE; '
                    f'date assessment {entry["assessment_id"]}; contents claims '
                    + escape(', '.join(str(i) for i in entry["coverage_claim_ids"])) + ')'
                    for entry in combo["scenarios"][side]) + '</td>')
            parts.append('</tr>')
    parts.append('</tbody></table>')
    parts.append('<h2>Reported contents and unresolved cases</h2><table><thead><tr>'
                 '<th>Verse</th><th>Witness</th><th>State</th><th>Source assertions and dates</th></tr></thead><tbody>')
    for verse in graph["verses"]:
        for pair in verse["reported_coverage"]:
            detail = []
            if pair["unknown_reason"]:
                detail.append('<p>' + escape(pair["unknown_reason"].replace('_', ' ')) + '.</p>')
            if pair["state"] == "contested":
                detail.append('<p>Explicit incompatible source claims retained. Deferred; no presence event.</p>')
            for claim in pair["claims"]:
                detail.append(f'<p><strong>{escape(claim["provider"])}: {escape(claim["assertion"])}</strong> '
                              f'({escape(claim.get("extent", "unspecified"))} extent). '
                              f'{source(claim["citation"])}<br>Retrieved {escape(claim["retrieved_at"])}; '
                              f'field {escape(claim["source_locator"])}; response {claim["source_response_id"]}; '
                              f'claim {claim["claim_id"]}. '
                              f'{escape(claim["qualifications"])}</p>'
                              '<details><summary>Exact reported field or statement</summary><code>' +
                              escape(json.dumps(claim["reported"], ensure_ascii=False, sort_keys=True)) + '</code></details>')
            if not pair["date_assessments"]:
                detail.append('<p>No reported date assessment; unrankable.</p>')
            for date in pair["date_assessments"]:
                interval = (f'{date["date_min"]}–{date["date_max"]} CE' if date["status"] == "valid"
                            else f'{date["status"]} numeric bounds; unrankable')
                detail.append(f'<p><strong>Date:</strong> {escape(interval)}; '
                              f'{escape(date.get("original_notation") or "notation not supplied")}. '
                              f'{escape(date["provider"])}; {source(date["citation"])}<br>'
                              f'Retrieved {escape(date["retrieved_at"])}; field {escape(date["source_locator"])}; '
                              f'response {date["source_response_id"]}; assessment {date["assessment_id"]}. '
                              f'{escape(date["qualifications"])}</p>')
            if verse.get("mapping_note"):
                detail.append('<p>Mapping: ' + escape(verse["mapping_note"]) + '</p>')
            parts.append(f'<tr class="{escape(pair["state"])}"><th>{escape(verse["osis_ref"])}</th>'
                         f'<td>{escape(pair["witness_id"])}</td><td>{escape(pair["state"])}; '
                         f'{escape(verse["editorial_status"])}; {escape(verse["ranking_state"])}</td>'
                         '<td>' + ''.join(detail) + '</td></tr>')
    parts.append('</tbody></table><h2>Source snapshots</h2><table><thead><tr>'
                 '<th>Response</th><th>Catalogue or publication</th><th>Retrieved</th><th>SHA-256</th>'
                 '</tr></thead><tbody>')
    for snapshot in graph["sources"]:
        parts.append(f'<tr><td>{snapshot["source_response_id"]}</td><td>' +
                     source(snapshot.get("canonical_url", snapshot["url"]) + ('?' + urlencode(snapshot["params"]) if snapshot["params"] else '')) +
                     f'</td><td>{escape(snapshot["retrieved_at"])}</td><td><code>'
                     f'{escape(snapshot["body_sha256"])}</code></td></tr>')
    parts.append('</tbody></table><p>Inventory source: ' + source(graph["inventory_source_citation"]) +
                 '</p><p>Mapping: ' + source(graph["mapping_citation"]) + '</p></body></html>')
    return '\n'.join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    graph = json.loads(args.graph_input.read_text(encoding="utf-8"))
    html = render(graph)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(json.dumps({"output": str(args.output),
                      "verses": graph["counts"]["verse_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
