import json
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path
from energy_report.uncertainty import emission_envelope, add_envelopes
from energy_report.report import DataError, main, load_csv, summarize, render_html

class EnvelopeTests(unittest.TestCase):
    def test_corner_arithmetic(self):
        result = emission_envelope(D('1000'), D('.04'), D('.08'), D('10'))
        self.assertEqual(D(result['emissions_low_kgco2e']), D('36'))
        self.assertEqual(D(result['emissions_high_kgco2e']), D('88'))
        self.assertEqual(D(result['factor_only_width_kgco2e']), D('40'))
        self.assertEqual(D(result['meter_only_width_at_mid_factor_kgco2e']), D('12'))

    def test_invalid(self):
        for values in [('NaN', '.1', '.2', '1'), ('1', '.2', '.1', '0'),
                       ('1', '.1', '.2', '101'), ('1', '-1', '.2', '0'), ('1', '.1', 'Infinity', '0')]:
            with self.subTest(values=values), self.assertRaises(DataError):
                emission_envelope(*map(D, values))

    def test_degenerate_and_zero(self):
        for kwh in ('0', '100'):
            r = emission_envelope(D(kwh), D('.1'), D('.1'))
            self.assertEqual(r['emissions_low_kgco2e'], r['emissions_high_kgco2e'])
        self.assertEqual(D(emission_envelope(D(100), D('.1'), D('.2'), D(100))['energy_low_kwh']), 0)

    def test_missing_months_not_filled(self):
        rows = load_csv(b'month,site,kwh,cost_eur\n2026-02,A,100,20\n')
        report = summarize(rows, 'x', expected_start='2026-01', expected_end='2026-03')
        add_envelopes(report, D('.1'), D('.2'))
        self.assertEqual(report['sites'][0]['kwh'], '100')
        self.assertEqual(len(report['sites'][0]['monthly']), 1)
        self.assertEqual(D(report['sites'][0]['emission_envelope']['emissions_high_kgco2e']), 20)
        self.assertIn('missing months excluded', render_html(report))

    def test_cli_validation_and_export(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            source = path / 'input.csv'
            source.write_text('month,site,kwh,cost_eur\n2026-01,A,1000,200\n')
            base = [str(source), '--out', str(path / 'out')]
            self.assertEqual(main(base + ['--factor-low', '.04']), 2)
            self.assertEqual(main(base + ['--meter-error-percent', '2']), 2)
            self.assertEqual(main(base + ['--factor-low', '.04', '--factor-high', '.08']), 2)
            flags = ['--factor', '.05', '--factor-source', 'Synthetic assumption', '--factor-low', '.04', '--factor-high', '.08', '--meter-error-percent', '10']
            self.assertEqual(main(base + flags), 0)
            self.assertEqual(json.loads((path/'out/report.json').read_text())['schema_version'], 3)
