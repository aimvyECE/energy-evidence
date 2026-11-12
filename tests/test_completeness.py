import unittest
from decimal import Decimal
from energy_report.report import load_csv, summarize, render_html, DataError

class CompletenessTests(unittest.TestCase):
    def rows(self):
        return load_csv(b'month,site,kwh,cost_eur\n2026-02,A,10,2\n2026-04,A,20,4\n')

    def test_declared_window_includes_edge_gaps(self):
        result = summarize(self.rows(), 'x', expected_start='2026-01', expected_end='2026-05')
        site = result['sites'][0]
        self.assertEqual(site['missing_months'], ['2026-01', '2026-03', '2026-05'])
        self.assertEqual(site['coverage_percent'], '40')
        self.assertEqual(site['kwh'], '30')
        self.assertEqual(len(site['monthly']), 2)  # No zero imputation.
        self.assertIn('2026-05', render_html(result))

    def test_default_span_does_not_infer_edges(self):
        result = summarize(self.rows(), 'x')
        self.assertEqual(result['sites'][0]['missing_months'], ['2026-03'])
        self.assertIsNone(result['expected_period'])

    def test_invalid_windows(self):
        for start, end in [('2026-01', None), (None, '2026-12'), ('2026-5', '2026-06'),
                           ('2026-06', '2026-01'), ('0000-01', '2026-01')]:
            with self.subTest(start=start,end=end), self.assertRaises(DataError):
                summarize(self.rows(), 'x', expected_start=start, expected_end=end)

    def test_no_silent_filtering(self):
        with self.assertRaises(DataError):
            summarize(self.rows(), 'x', expected_start='2026-03', expected_end='2026-05')

    def test_factor_provenance_retained_and_escaped(self):
        result = summarize(self.rows(), 'x', Decimal('0.05'), factor_source='<b>invented demo</b>')
        self.assertEqual(result['factor_source'], '<b>invented demo</b>')
        self.assertIn('&lt;b&gt;invented demo&lt;/b&gt;', render_html(result))
        self.assertEqual(result['sites'][0]['estimated_kgco2e'], '1.50')

    def test_invalid_factor_source(self):
        for factor, source in [(None, 'citation'), (Decimal('0.1'), ' ')]:
            with self.subTest(source=source), self.assertRaises(DataError):
                summarize(self.rows(), 'x', factor, factor_source=source)

    def test_empty_api_input(self):
        with self.assertRaises(DataError):
            summarize([], 'x')

    def test_year_boundary_and_single_month(self):
        rows = load_csv(b'month,site,kwh,cost_eur\n2026-12,A,10,2\n2027-02,A,20,4\n')
        result = summarize(rows, 'x')
        self.assertEqual(result['sites'][0]['missing_months'], ['2027-01'])
        self.assertEqual(summarize(rows[:1], 'x')['sites'][0]['coverage_percent'], '100')
