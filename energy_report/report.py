"""No-network CSV validation and reporting. Python standard library only."""
import argparse
import csv
import hashlib
import html
import io
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


class DataError(ValueError):
    pass


@dataclass(frozen=True)
class Reading:
    month: str
    site: str
    kwh: Decimal
    cost_eur: Decimal


def number(value, field, row):
    try:
        result = Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        raise DataError(f"Row {row}: {field} must be a decimal number") from None
    if not result.is_finite() or result < 0:
        raise DataError(f"Row {row}: {field} must be finite and nonnegative")
    return result


def load_csv(raw):
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), strict=True)
        expected = ['month', 'site', 'kwh', 'cost_eur']
        if reader.fieldnames != expected:
            raise DataError('Expected columns, in order: ' + ','.join(expected))
        rows, seen = [], set()
        for index, item in enumerate(reader, 2):
            if None in item or any(value is None for value in item.values()):
                raise DataError(f'Row {index}: wrong number of fields')
            month, site = item['month'].strip(), item['site'].strip()
            if not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', month) or month[:4] == '0000':
                raise DataError(f'Row {index}: month must be YYYY-MM, year 0001–9999')
            if not site:
                raise DataError(f'Row {index}: site must not be blank')
            if (month, site) in seen:
                raise DataError(f'Row {index}: duplicate site/month ({site}, {month})')
            seen.add((month, site))
            rows.append(Reading(month, site, number(item['kwh'], 'kwh', index), number(item['cost_eur'], 'cost_eur', index)))
        if not rows:
            raise DataError('CSV must contain at least one reading')
        return sorted(rows, key=lambda row: (row.site, row.month))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise DataError(f'Invalid UTF-8 CSV: {exc}') from None


def month_index(month):
    year, value = map(int, month.split('-'))
    return year * 12 + value - 1


def percent(current, previous):
    return None if previous == 0 else str((current - previous) * 100 / previous)


def month_range(start, end):
    for value in (start, end):
        if not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', value) or value[:4] == '0000':
            raise DataError('Expected period must use YYYY-MM, year 0001–9999')
    first, last = month_index(start), month_index(end)
    if first > last:
        raise DataError('Expected start must not follow expected end')
    return [f'{index // 12:04d}-{index % 12 + 1:02d}' for index in range(first, last + 1)]


def summarize(rows, source_sha256, factor=None, threshold=Decimal('25'),
              expected_start=None, expected_end=None, factor_source=None):
    if not rows:
        raise DataError('At least one reading is required')
    if (expected_start is None) != (expected_end is None):
        raise DataError('Supply both expected start and expected end')
    expected = None if expected_start is None else month_range(expected_start, expected_end)
    if expected is not None and any(row.month < expected_start or row.month > expected_end for row in rows):
        raise DataError('Observation outside expected reporting period; no rows were silently dropped')
    if factor_source is not None and (factor is None or not factor_source.strip()):
        raise DataError('Factor source requires a factor and a nonblank description')
    if factor is not None and (not factor.is_finite() or factor < 0):
        raise DataError('Emission factor must be finite and nonnegative')
    if not threshold.is_finite() or threshold < 0:
        raise DataError('Threshold must be finite and nonnegative')
    sites, warnings = [], []
    for site in sorted({row.site for row in rows}):
        records = sorted((row for row in rows if row.site == site), key=lambda row: row.month)
        total_kwh = sum((row.kwh for row in records), Decimal(0))
        total_cost = sum((row.cost_eur for row in records), Decimal(0))
        window = expected if expected is not None else month_range(records[0].month, records[-1].month)
        observed = {row.month for row in records}
        missing = [month for month in window if month not in observed]
        monthly = []
        for index, row in enumerate(records):
            change = None
            if index:
                previous = records[index - 1]
                if month_index(row.month) - month_index(previous.month) != 1:
                    warnings.append(f'{site}: nonconsecutive observations {previous.month} → {row.month}; no month-on-month comparison')
                else:
                    change = percent(row.kwh, previous.kwh)
                    if change is not None and abs(Decimal(change)) >= threshold:
                        warnings.append(f'{site} {row.month}: consumption change {Decimal(change):.1f}% exceeds or equals screening threshold')
            monthly.append({'month': row.month, 'kwh': str(row.kwh), 'cost_eur': str(row.cost_eur), 'change_percent': change})
        if expected is not None and missing:
            warnings.append(f'{site}: {len(missing)} missing months in declared reporting period; missing is not zero consumption')
        sites.append({'site': site, 'missing_months': missing,
                      'expected_months': len(window), 'coverage_percent': str(Decimal(len(records)) * 100 / len(window)), 'observed_months': len(records), 'first_month': records[0].month, 'last_month': records[-1].month,
                      'kwh': str(total_kwh), 'cost_eur': str(total_cost),
                      'blended_eur_per_kwh': None if total_kwh == 0 else str(total_cost / total_kwh),
                      'estimated_kgco2e': None if factor is None else str(total_kwh * factor), 'monthly': monthly})
    coverages = {(s['first_month'], s['last_month'], tuple(m['month'] for m in s['monthly'])) for s in sites}
    if len(coverages) > 1:
        warnings.append('Sites have unequal observed periods; aggregate totals are not like-for-like site comparisons')
    return {'schema_version': 2, 'expected_period': None if expected is None else {'start': expected_start, 'end': expected_end},
            'factor_source': factor_source, 'coverage_basis': 'declared period' if expected is not None else 'each site observed span', 'source_sha256': source_sha256, 'currency': 'EUR',
            'emission_factor_kgco2e_per_kwh': None if factor is None else str(factor),
            'screening_threshold_percent': str(threshold), 'sites': sites, 'warnings': warnings,
            'limitations': ['Prototype, not an energy audit or regulatory carbon inventory.',
                           'Changes are screening signals, not proof of waste or faults; weather, occupancy and billing periods are not normalized.',
                           'Cost/kWh includes every cost in the input and is not necessarily the contractual energy tariff.',
                           'Optional single emission factor is user supplied; no default factor or source is implied.']}


def render_html(result):
    escape = lambda value: html.escape(str(value), quote=True)
    cards = []
    for site in result['sites']:
        rows = ''.join('<tr>' + ''.join(f'<td>{escape(value) if value is not None else "—"}</td>' for value in
                   [m['month'], m['kwh'], m['cost_eur'], m['change_percent']]) + '</tr>' for m in site['monthly'])
        cards.append(f"<section><h2>{escape(site['site'])}</h2><p>{escape(site['kwh'])} kWh · {escape(site['cost_eur'])} EUR · {site['observed_months']} observed months</p>"
                     f"<p>Coverage: {escape(site['coverage_percent'])}% of {site['expected_months']} months ({escape(result['coverage_basis'])}). Missing: {escape(', '.join(site['missing_months']) or 'none')}.</p>"
                     '<table><thead><tr><th>Month</th><th>kWh</th><th>EUR</th><th>Change %</th></tr></thead><tbody>' + rows + '</tbody></table></section>')
    warnings = ''.join(f'<li>{escape(item)}</li>' for item in result['warnings']) or '<li>No screening flags. This does not establish data completeness or absence of issues.</li>'
    limitations = ''.join(f'<li>{escape(item)}</li>' for item in result['limitations'])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Energy CSV report</title>
<style>body{{font:16px system-ui;margin:40px auto;max-width:960px;padding:0 20px;color:#153334;background:#f6f9f7}}section{{background:white;padding:20px;margin:20px 0;border:1px solid #cddbd6;border-radius:12px}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:8px;border-bottom:1px solid #ddd}}code{{overflow-wrap:anywhere}}</style>
<h1>Energy CSV report</h1><p>Local prototype · monthly observations · EUR</p>{''.join(cards)}<h2>Review flags</h2><ul>{warnings}</ul><h2>Method and limitations</h2><ul>{limitations}</ul><p>Supplied factor (kgCO₂e/kWh): {escape(result['emission_factor_kgco2e_per_kwh'])}</p><p>Factor provenance (user declaration, not verified): {escape(result['factor_source'] or 'not supplied')}</p><p>Source SHA-256: <code>{escape(result['source_sha256'])}</code></p></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--out', type=Path, default=Path('report-output'))
    parser.add_argument('--factor', help='Optional user-sourced kgCO2e/kWh factor; no default')
    parser.add_argument('--threshold', default='25', help='Absolute consecutive-month change screening threshold (%)')
    parser.add_argument('--expected-start', help='First required reporting month, YYYY-MM; requires --expected-end')
    parser.add_argument('--expected-end', help='Last required reporting month, YYYY-MM; requires --expected-start')
    parser.add_argument('--factor-source', help='User-declared factor citation, year, geography and method (not verified)')
    args = parser.parse_args(argv)
    try:
        raw = args.csv.read_bytes()
        rows = load_csv(raw)
        factor = None if args.factor is None else number(args.factor, 'factor', 'CLI')
        threshold = number(args.threshold, 'threshold', 'CLI')
        result = summarize(rows, hashlib.sha256(raw).hexdigest(), factor, threshold,
                           args.expected_start, args.expected_end, args.factor_source)
        args.out.mkdir(parents=True, exist_ok=True)
        # Refuse overwrites so repeated runs cannot silently replace an earlier report.
        json_path, html_path = args.out / 'report.json', args.out / 'report.html'
        if json_path.exists() or html_path.exists():
            raise DataError('Output exists; choose a new --out directory')
        json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        html_path.write_text(render_html(result), encoding='utf-8')
        print(f'Wrote {json_path} and {html_path}')
        return 0
    except (DataError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2
