# Energy Evidence — local CSV reporting

An early-stage, AI-assisted portfolio prototype for turning **monthly energy exports** into a traceable report. It runs locally, uses no API and requires no external Python packages. It is not deployed, not used by customers, and not a certified audit product.

## What works

- Validates a strict CSV contract and refuses duplicates, malformed rows and non-finite numbers.
- Computes per-site energy and cost totals using decimal arithmetic.
- Flags large positive **or negative** changes between consecutive observed months.
- Warns about gaps and unequal site coverage; never compares nonconsecutive months as month-on-month growth.
- Exports machine-readable JSON and a standalone, escaped HTML report.
- Records a SHA-256 fingerprint of the input for traceability.
- Optionally estimates emissions using an **explicit user-supplied factor**, with no hidden default.

## Quick start (Python 3.10+)

```sh
python -m energy_report examples/synthetic_monthly.csv --out demo-output
python -m unittest discover -s tests -v
```

Open `demo-output/report.html` in a browser. Every figure in the included CSV is invented. No real school, customer or personal record is included. A pre-generated sample is in `examples/report/`.

Repeated runs refuse to overwrite existing reports. Select a fresh output directory. The source file is never modified.

### CSV contract

```csv
month,site,kwh,cost_eur
2026-01,Example site,1000,260
```

UTF-8 (optional BOM), comma delimiter, decimal dot, exact column order. One row per site and calendar month. `kwh` and `cost_eur` are nonnegative decimals. All rows must concern the same energy scope (e.g. purchased electricity); aggregate multiple meters before importing. Costs must use a consistent basis (all including or all excluding VAT). `kwh` is a period total, **not a cumulative meter reading**. Negative credit notes, gas volume conversion and multi-currency files are unsupported: reconcile them upstream rather than silently changing signs.

Optional illustrative calculation:

```sh
python -m energy_report examples/synthetic_monthly.csv --out demo-factor --factor 0.05
```

The `0.05` factor above is a **made-up demonstration assumption**, not a recommended French electricity factor. The user must select, document and validate the applicable factor, year, geography and accounting method. This single-factor prototype is not a Scope 2 inventory and does not distinguish market-based from location-based accounting.

## Expected demonstration

- Demo workshop: 3,700 kWh and €962.
- Demo office: 1,690 kWh and €507.
- Workshop March change: approximately +45.45%, flagged at the default 25% screening threshold.

These flags are not a diagnosis. Weather, occupancy, working days and actual billing intervals are not normalized. A cost/kWh ratio can include standing charges and is not necessarily an energy tariff. Incomplete coverage outside the first/last observed months cannot be inferred.

## Design and boundaries

Standard library only: `csv`, `Decimal`, `hashlib`, `html`, `json`, `argparse`. No borrowed model, OCR engine, cloud connector, telemetry or network calls. CSV extraction from invoices is **not implemented**. This repository is a small reporting building block, not a production SaaS.

Tests cover calculations, duplicate rejection, dates, invalid numeric values, sparse periods, zero baselines, unequal coverage, HTML escaping and CLI exports. GitHub Actions configuration is supplied but has not been run remotely. Local test evidence is in `VALIDATION.md`.

### Security and privacy

Run on trusted, bounded-size exports: the entire CSV is loaded into memory. HTML data is escaped. Reports reproduce site names and consumption data; treat them as potentially confidential and do not publish real input/output files. This implementation has no authentication, encryption or production retention controls. It refuses existing outputs but is not designed for concurrent writers or transactional output recovery.

## Development roadmap (not delivered)

1. Meter-level and billing-interval schema; completeness calendar.
2. Factor provenance and separate accounting methods.
3. Weather/occupancy normalization with uncertainty bounds.
4. Invoice extraction with human review and source highlighting.
5. Accessibility and visual browser review of HTML output.

## Method references

- Python `Decimal`: https://docs.python.org/3/library/decimal.html
- GHG Protocol Scope 2 Guidance (context for future accounting work, not compliance claim): https://ghgprotocol.org/scope-2-guidance

## Authorship and license

Developed as an AI-assisted prototype for a personal engineering portfolio. No claim of past deployment, customer adoption, model training or professional certification. MIT license covers the code and synthetic examples; see `LICENSE`.
