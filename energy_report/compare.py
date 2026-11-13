"""Compare matching calendar months across two years without filling missing data."""
import argparse
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

from .report import DataError, load_csv, percent


def compare_years(rows, baseline_year, comparison_year):
    """Compare validated Reading objects, retaining excluded months explicitly."""
    for year in (baseline_year, comparison_year):
        if type(year) is not int or not 1 <= year <= 9999:
            raise DataError('Years must be integers from 1 to 9999')
    if baseline_year >= comparison_year:
        raise DataError('Comparison year must be after baseline year')
    if not rows:
        raise DataError('At least one reading is required')
    selected = [r for r in rows if int(r.month[:4]) in (baseline_year, comparison_year)]
    if not selected:
        raise DataError('No observations in the selected years')
    # Check API callers as well as the CSV entry point: duplicates must not disappear.
    keys = [(r.site, r.month) for r in rows]
    if len(keys) != len(set(keys)):
        raise DataError('Duplicate site/month observations')
    sites = []
    for site in sorted({r.site for r in selected}):
        years = {year: {r.month[5:]: r for r in selected
                        if r.site == site and int(r.month[:4]) == year}
                 for year in (baseline_year, comparison_year)}
        baseline, current = years[baseline_year], years[comparison_year]
        common = sorted(baseline.keys() & current.keys())
        totals = {}
        for field in ('kwh', 'cost_eur'):
            old = sum((getattr(baseline[m], field) for m in common), Decimal(0))
            new = sum((getattr(current[m], field) for m in common), Decimal(0))
            # No comparable observations is not a measured zero.
            totals[field] = None if not common else {
                'baseline': str(old), 'comparison': str(new),
                'change': str(new - old), 'change_percent': percent(new, old)}
        sites.append({'site': site, 'matched_months': common,
                      'matched_month_count': len(common),
                      'full_calendar_year': len(common) == 12,
                      'baseline_only_months': sorted(baseline.keys() - current.keys()),
                      'comparison_only_months': sorted(current.keys() - baseline.keys()),
                      'totals_on_matched_months': totals})
    ignored = sorted({r.month[:4] for r in rows
                      if int(r.month[:4]) not in (baseline_year, comparison_year)})
    return {'comparison_schema_version': 1, 'baseline_year': baseline_year,
            'comparison_year': comparison_year, 'ignored_years': ignored,
            'sites': sites, 'limitations': [
                'Only matching calendar months are compared; missing data is not zero.',
                'Changes are not verified energy savings or a diagnosis.',
                'Weather, occupancy, billing intervals and leap years are not normalized.',
                'Cost changes may reflect price changes, not consumption efficiency.',
                'Input must use a consistent energy scope and tax basis across years.',
                'No cross-site aggregate is supplied: sites may have different matched months.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--baseline-year', type=int, required=True)
    parser.add_argument('--comparison-year', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True, help='New JSON file; never overwritten')
    args = parser.parse_args(argv)
    try:
        raw = args.csv.read_bytes()
        result = compare_years(load_csv(raw), args.baseline_year, args.comparison_year)
        result['source_sha256'] = hashlib.sha256(raw).hexdigest()
        # Exclusive creation also protects against a concurrent writer.
        with args.out.open('x', encoding='utf-8') as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False)
            handle.write('\n')
        print(f'Wrote {args.out}')
        return 0
    except (DataError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
