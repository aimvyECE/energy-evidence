# Contributing

This is a small, early prototype. Contributions are welcome; no contributor community or production adoption is claimed.

## Reproduce first

1. Clone the repository and use Python 3.10 or newer.
2. Run `python -m unittest discover -s tests -v` (no dependency install required).
3. Run `python -m energy_report examples/synthetic_monthly.csv --out demo-output`.
4. Open the HTML and inspect the JSON alongside the CSV. Use a new output directory for each run.

## Useful starter contributions

- Add boundary tests for malformed CSV and expected reporting calendars.
- Improve keyboard/screen-reader access and responsive report tables.
- Propose a schema for factor metadata with citations, units and accounting method.
- Design source-row evidence references before attempting invoice extraction.

Discuss scope in an issue before introducing dependencies or changing accounting assumptions. Provide a minimal **synthetic** example, expected and actual output, and the Python version. Do not upload real invoices, identities, credentials or consumption records.

A pull request should explain the decision, update tests and documentation, and disclose material AI assistance. Tests must pass; new computed values need an independently checkable fixture. Do not rename screening signals as diagnoses or claim compliance without supporting validation. Retain upstream credits and check licences for any added material.

## Review checklist

- [ ] Missing observations are not silently replaced with zeros.
- [ ] No rows are dropped without an explicit error or documented user choice.
- [ ] Units and reporting periods remain visible.
- [ ] HTML escapes every user-provided value.
- [ ] Examples contain synthetic data only.
- [ ] JSON schema changes and limitations are documented.
