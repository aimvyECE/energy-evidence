import copy
import json
import tempfile
import unittest
from pathlib import Path

from energy_report.report import DataError, load_csv, main, render_html, summarize
from energy_report.site_register import add_site_register


class SiteRegisterTests(unittest.TestCase):
    def report(self):
        return summarize(load_csv(b'month,site,kwh,cost_eur\n2026-01,A,10,2\n2026-03,A,20,4\n2026-01,C,0,0\n'), 'synthetic')

    def test_absent_site_is_not_zero_and_unlisted_readings_are_retained(self):
        result = self.report()
        original_sites = copy.deepcopy(result['sites'])
        add_site_register(result, ['A', 'B'])
        self.assertEqual(result['site_register']['missing_sites'], ['B'])
        self.assertEqual(result['site_register']['unexpected_sites'], ['C'])
        self.assertEqual(result['site_register']['observed_expected_sites'], ['A'])
        self.assertEqual(result['sites'], original_sites)
        self.assertEqual(result['sites'][0]['missing_months'], ['2026-02'])
        self.assertIn('unknown, not zero', '\n'.join(result['warnings']))

    def test_measured_zero_still_counts_as_present(self):
        result = add_site_register(self.report(), ['C', 'A'])
        self.assertEqual(result['site_register']['missing_sites'], [])
        self.assertEqual(result['site_register']['unexpected_sites'], [])

    def test_matching_is_trimmed_but_case_sensitive(self):
        result = add_site_register(self.report(), [' A ', 'a'])
        self.assertEqual(result['site_register']['expected_sites'], ['A', 'a'])
        self.assertEqual(result['site_register']['missing_sites'], ['a'])

    def test_invalid_register_does_not_mutate_report(self):
        for names in [[], '', 'AB', b'AB', [' '], [1], ['A', ' A ']]:
            with self.subTest(names=names):
                result = self.report()
                original = copy.deepcopy(result)
                with self.assertRaises(DataError):
                    add_site_register(result, names)
                self.assertEqual(result, original)

    def test_deterministic_order_and_all_declared_sites_missing(self):
        a = add_site_register(self.report(), ['Y', 'X'])
        b = add_site_register(self.report(), ['X', 'Y'])
        self.assertEqual(a, b)
        self.assertEqual(a['site_register']['missing_sites'], ['X', 'Y'])

    def test_repeat_application_is_rejected(self):
        result = add_site_register(self.report(), ['A'])
        original = copy.deepcopy(result)
        with self.assertRaises(DataError):
            add_site_register(result, ['B'])
        self.assertEqual(result, original)

    def test_html_escapes_names_and_explains_presence_not_completeness(self):
        rendered = render_html(add_site_register(self.report(), ['<script>alert(1)</script>']))
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)
        self.assertIn('not full-period completeness', rendered)

    def test_cli_optional_register_and_envelopes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'input.csv'
            source.write_text('month,site,kwh,cost_eur\n2026-01,A,10,2\n')
            args = [str(source), '--out', str(root/'out'), '--expected-site', 'A', '--expected-site', 'B',
                    '--factor', '0.05', '--factor-source', 'synthetic', '--factor-low', '0.04', '--factor-high', '0.06']
            self.assertEqual(main(args), 0)
            report = json.loads((root/'out/report.json').read_text())
            self.assertEqual(report['schema_version'], 3)
            self.assertEqual(report['site_register']['schema_version'], 1)
            self.assertEqual(report['site_register']['missing_sites'], ['B'])
            self.assertIn('emission_envelope', report['sites'][0])
            self.assertEqual(main([str(source), '--out', str(root/'default')]), 0)
            self.assertNotIn('site_register', json.loads((root/'default/report.json').read_text()))
            self.assertEqual(main([str(source), '--out', str(root/'bad'), '--expected-site', ' ']), 2)
            self.assertFalse((root/'bad').exists())
