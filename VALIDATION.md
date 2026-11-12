# Local verification

Date: 2026-11-12. Runtime: Python 3.12.14, Linux.

- `python -m unittest discover -s tests -v`: 17 tests passed.
- `python -m energy_report examples/synthetic_monthly.csv --out examples/report`: exit 0; JSON and standalone HTML generated.
- `python -m compileall -q energy_report tests`: exit 0.
- The first test run had a string-format expectation (`10.0` versus equivalent decimal `10`); the test was corrected to compare numeric values and all tests were rerun.

Not performed: deployment, remote GitHub Actions execution, browser visual/accessibility review, real customer data validation, external security audit, large-data load tests. Compatibility with Python 3.10 and 3.13 is intended and configured in CI, but only 3.12 was tested locally.

All demonstration records are synthetic. No network service, model download or paid resource is required.

## Completeness/provenance extension

Local validation: 25 unittest tests passed on Python 3.12. Eight new tests cover declared edge gaps, inferred spans, invalid windows, rejection of out-of-window observations, provenance retention and HTML escaping, invalid provenance, empty API input, and year boundaries. The CLI successfully generated `examples/calendar-report/` from the synthetic fixture with a January–April declared window and an explicitly invented emission factor.

No external audit, real-world field test or production performance benchmark is claimed. Coverage is calendar completeness, not evidence of meter accuracy. GitHub CI must be checked separately for each published revision.

## Scenario envelope validation

30 tests pass locally (Python 3.12), including 5 envelope tests: exact corner arithmetic, invalid/inverted/nonfinite bounds, zero-width and zero-energy cases, missing-month exclusion, CLI guardrails and JSON/HTML export. The worked fixture uses only invented data. No claim of statistical calibration or visual browser QA is made.
