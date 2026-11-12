import contextlib
import hashlib
import io
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from energy_report.report import DataError, load_csv, main, render_html, summarize

HEADER = 'month,site,kwh,cost_eur\n'

class ReportTests(unittest.TestCase):
    def parse(self, data):
        return load_csv((HEADER + data).encode())

    def test_exact_totals_and_factor(self):
        data = self.parse('2026-01,A,0.1,0.03\n2026-02,A,0.2,0.06\n')
        result = summarize(data, 'abc', Decimal('0.05'))
        self.assertEqual(result['sites'][0]['kwh'], '0.3')
        self.assertEqual(result['sites'][0]['cost_eur'], '0.09')
        self.assertEqual(result['sites'][0]['estimated_kgco2e'], '0.015')

    def test_no_implicit_carbon(self):
        self.assertIsNone(summarize(self.parse('2026-01,A,1,2\n'), 'x')['sites'][0]['estimated_kgco2e'])

    def test_zero_baseline(self):
        result = summarize(self.parse('2026-01,A,0,2\n2026-02,A,10,2\n'), 'x')
        self.assertIsNone(result['sites'][0]['monthly'][1]['change_percent'])

    def test_zero_total(self):
        result = summarize(self.parse('2026-01,A,0,2\n'), 'x')
        self.assertIsNone(result['sites'][0]['blended_eur_per_kwh'])

    def test_missing_month_not_compared(self):
        result = summarize(self.parse('2026-01,A,1,2\n2026-03,A,10,2\n'), 'x')
        self.assertIsNone(result['sites'][0]['monthly'][1]['change_percent'])
        self.assertIn('nonconsecutive', result['warnings'][0])

    def test_year_boundary(self):
        result = summarize(self.parse('2026-12,A,10,2\n2027-01,A,11,2\n'), 'x')
        self.assertEqual(Decimal(result['sites'][0]['monthly'][1]['change_percent']), Decimal('10'))

    def test_duplicate(self):
        with self.assertRaises(DataError):
            self.parse('2026-01,A,1,2\n2026-01,A,2,3\n')

    def test_invalid_values(self):
        for value in ['-1', 'NaN', 'Infinity', '', 'one']:
            with self.subTest(value=value), self.assertRaises(DataError):
                self.parse(f'2026-01,A,{value},2\n')

    def test_invalid_dates(self):
        for month in ['2026-13', '2026-1', '0000-01', '2026-00']:
            with self.subTest(month=month), self.assertRaises(DataError):
                self.parse(f'{month},A,1,2\n')

    def test_shape_and_header(self):
        for raw in [HEADER, 'month,site,kwh\n', HEADER + '2026-01,A,1\n', HEADER + '2026-01,A,1,2,3\n']:
            with self.subTest(raw=raw), self.assertRaises(DataError):
                load_csv(raw.encode())

    def test_blank_site(self):
        with self.assertRaises(DataError):
            self.parse('2026-01, ,1,2\n')

    def test_utf8_bom(self):
        self.assertEqual(load_csv(('\ufeff' + HEADER + '2026-01,École,1,2\n').encode())[0].site, 'École')

    def test_unequal_coverage(self):
        result = summarize(self.parse('2026-01,A,1,2\n2026-02,B,1,2\n'), 'x')
        self.assertTrue(any('unequal' in warning for warning in result['warnings']))

    def test_html_escaping(self):
        result = summarize(self.parse('2026-01,<script>alert(1)</script>,1,2\n'), 'x')
        output = render_html(result)
        self.assertNotIn('<script>', output)
        self.assertIn('&lt;script&gt;', output)

    def test_negative_change_is_flagged(self):
        result = summarize(self.parse('2026-01,A,100,20\n2026-02,A,50,10\n'), 'x')
        self.assertEqual(len(result['warnings']), 1)

    def test_cli_files_hash_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'data.csv'
            path.write_text(HEADER + '2026-01,A,1,2\n')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(path), '--out', str(root / 'out')]), 0)
                self.assertEqual(main([str(path), '--out', str(root / 'out')]), 2)
            self.assertIn(hashlib.sha256(path.read_bytes()).hexdigest(), (root / 'out/report.json').read_text())

    def test_cli_bad_input_creates_no_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'data.csv'
            path.write_text('bad')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(path), '--out', str(root / 'out')]), 2)
            self.assertFalse((root / 'out').exists())

if __name__ == '__main__':
    unittest.main()
