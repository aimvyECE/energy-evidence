import hashlib
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from energy_report.compare import compare_years, main
from energy_report.report import DataError, load_csv


HEADER = 'month,site,kwh,cost_eur\n'

def readings(text):
    return load_csv((HEADER + text).encode())


class ComparisonTests(unittest.TestCase):
    def test_matches_months_not_unequal_annual_totals(self):
        rows = readings('2024-01,A,100,20\n2024-02,A,1000,200\n2025-01,A,80,24\n')
        site = compare_years(rows, 2024, 2025)['sites'][0]
        self.assertEqual(site['matched_months'], ['01'])
        self.assertEqual(site['baseline_only_months'], ['02'])
        self.assertFalse(site['full_calendar_year'])
        self.assertEqual(Decimal(site['totals_on_matched_months']['kwh']['change_percent']), -20)
        self.assertEqual(Decimal(site['totals_on_matched_months']['cost_eur']['change_percent']), 20)

    def test_no_overlap_is_unknown_not_zero(self):
        rows = readings('2024-01,A,10,2\n2025-02,A,20,4\n')
        site = compare_years(rows, 2024, 2025)['sites'][0]
        self.assertEqual(site['matched_month_count'], 0)
        self.assertEqual(site['comparison_only_months'], ['02'])
        self.assertIsNone(site['totals_on_matched_months']['kwh'])

    def test_zero_baseline_has_no_percentage(self):
        rows = readings('2024-01,A,0,0\n2025-01,A,20,4\n')
        value = compare_years(rows, 2024, 2025)['sites'][0]['totals_on_matched_months']['kwh']
        self.assertEqual(value['change'], '20')
        self.assertIsNone(value['change_percent'])

    def test_separate_sites_and_ignored_years(self):
        rows = readings('2024-01,A,10,2\n2025-01,B,20,4\n2023-01,C,99,9\n')
        result = compare_years(rows, 2024, 2025)
        self.assertEqual(result['ignored_years'], ['2023'])
        self.assertEqual([s['site'] for s in result['sites']], ['A', 'B'])
        self.assertTrue(all(s['totals_on_matched_months']['kwh'] is None for s in result['sites']))

    def test_full_year_and_determinism(self):
        rows = readings(''.join(f'{y}-{m:02d},A,0.1,0.2\n' for y in (2024, 2025) for m in range(1, 13)))
        result = compare_years(rows, 2024, 2025)
        self.assertEqual(result, compare_years(list(reversed(rows)), 2024, 2025))
        self.assertTrue(result['sites'][0]['full_calendar_year'])
        self.assertEqual(result['sites'][0]['totals_on_matched_months']['kwh']['baseline'], '1.2')

    def test_nonadjacent_years_are_not_annualized(self):
        rows = readings('0001-01,A,100,20\n0003-01,A,80,16\n')
        result = compare_years(rows, 1, 3)
        self.assertEqual(result['baseline_year'], 1)
        self.assertEqual(result['comparison_year'], 3)
        self.assertEqual(Decimal(result['sites'][0]['totals_on_matched_months']['kwh']['change_percent']), -20)

    def test_rejects_invalid_years_and_empty_selection(self):
        rows = readings('2024-01,A,10,2\n')
        for a, b in [(2024,2024), (2025,2024), (0,2025), (2024,10000), ('2024',2025), (True,2025)]:
            with self.subTest(a=a,b=b), self.assertRaises(DataError):
                compare_years(rows,a,b)
        with self.assertRaises(DataError):
            compare_years([], 2024, 2025)
        with self.assertRaises(DataError):
            compare_years(rows, 2020, 2021)
        with self.assertRaises(DataError):
            compare_years(rows + rows, 2024, 2025)

    def test_cli_provenance_no_overwrite_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder)/'input.csv', Path(folder)/'result.json'
            source.write_text(HEADER+'2024-01,A,100,20\n2025-01,A,80,24\n')
            args = [str(source),'--baseline-year','2024','--comparison-year','2025','--out',str(target)]
            self.assertEqual(main(args),0)
            original = target.read_bytes()
            result = json.loads(original)
            self.assertEqual(result['source_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(main(args),2)
            self.assertEqual(original,target.read_bytes())
            source.write_text(HEADER+'2024-01,A,NaN,20\n')
            self.assertEqual(main(args[:-1]+[str(Path(folder)/'bad.json')]),2)
            self.assertFalse((Path(folder)/'bad.json').exists())
