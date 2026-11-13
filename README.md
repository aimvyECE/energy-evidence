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

These flags are not a diagnosis. Weather, occupancy, working days and actual billing intervals are not normalized. A cost/kWh ratio can include standing charges and is not necessarily an energy tariff. Without an explicit expected period, incomplete coverage outside the first/last observed months cannot be inferred.

## Design and boundaries

Standard library only: `csv`, `Decimal`, `hashlib`, `html`, `json`, `argparse`. No borrowed model, OCR engine, cloud connector, telemetry or network calls. CSV extraction from invoices is **not implemented**. This repository is a small reporting building block, not a production SaaS.

Tests cover calculations, duplicate rejection, dates, invalid numeric values, sparse periods, zero baselines, unequal coverage, HTML escaping and CLI exports. GitHub Actions runs the test suite on pushes and pull requests; consult the Actions tab for the current result. Local test evidence is in `VALIDATION.md`.

### Security and privacy

Run on trusted, bounded-size exports: the entire CSV is loaded into memory. HTML data is escaped. Reports reproduce site names and consumption data; treat them as potentially confidential and do not publish real input/output files. This implementation has no authentication, encryption or production retention controls. It refuses existing outputs but is not designed for concurrent writers or transactional output recovery.

## Development roadmap (not delivered)

1. Meter-level and billing-interval schema.
2. Structured factor provenance and separate accounting methods.
3. Weather/occupancy normalization with uncertainty bounds.
4. Invoice extraction with human review and source highlighting.
5. Accessibility and visual browser review of HTML output.

## Method references

- Python `Decimal`: https://docs.python.org/3/library/decimal.html
- GHG Protocol Scope 2 Guidance (context for future accounting work, not compliance claim): https://ghgprotocol.org/scope-2-guidance

## Authorship and license

Developed as an AI-assisted prototype for a personal engineering portfolio. No claim of past deployment, customer adoption, model training or professional certification. MIT license covers the code and synthetic examples; see `LICENSE`.

## Completeness and factor provenance (schema v2)

```sh
python -m energy_report examples/synthetic_monthly.csv --out calendar-demo \
  --expected-start 2026-01 --expected-end 2026-04 \
  --factor 0.05 --factor-source "Synthetic teaching assumption; not a real inventory factor"
```

Both period boundaries are required together. The declared window applies to every observed site; an observation outside it is rejected rather than silently excluded. JSON includes `missing_months`, `expected_months`, and `coverage_percent` per site. Missing months are **not imputed** into monthly readings or totals. Without a declared window, completeness covers each site's first-to-last observation only. Entirely absent sites cannot be detected without a separate site register.

`factor_source` preserves a user declaration, not a verified citation. It is optional for compatibility, but should be supplied whenever emissions figures are shared. It requires a factor and must not be blank. The factor is still a single assumption for all observations, not a multi-year or site-specific inventory model.

Schema v2 adds completeness and provenance fields; existing numerical site fields remain. A synthetic worked calendar report is included in `examples/calendar-report/`. For contribution workflow and review criteria, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Assumption stress test (optional schema v3)

Rather than presenting one carbon number as certain, propagate explicit bounds:

```sh
python -m energy_report examples/synthetic_monthly.csv --out envelope-demo \
  --expected-start 2026-01 --expected-end 2026-04 \
  --factor 0.05 --factor-source "Synthetic teaching assumptions only" \
  --factor-low 0.04 --factor-high 0.08 --meter-error-percent 10
```

All factors above are **invented**, not sourced inventory factors. Each site's JSON and HTML includes an observed-period emissions envelope. For 1,000 observed kWh, ±10% energy error and factors 0.04–0.08, the result is **36–88 kgCO₂e**. This is deterministic interval propagation `E × (1 ± r) × factor_bound`, **not a confidence interval, probability distribution or forecast**. Bounds assume simultaneous extremes, allowing systematic bias shared across readings. Meter error must be 0–100%; the central factor must be inside the bounds; an explicit factor source declaration is mandatory.

JSON also exposes one-at-a-time widths from the factor range and meter error at the midpoint factor. These help decide which assumption deserves further investigation; they are not independent variances or statistical importance scores. The API is `energy_report.uncertainty.emission_envelope` (Decimal arguments).

**Missing consumption remains missing.** Bounds apply only to observed totals and do not turn a partial year into an annual inventory. No automatic imputation, probability model, regulatory assurance, or validation of supplied bounds is claimed. Existing commands retain schema v2; opting into bounds produces schema v3 with additive site fields. See the entirely synthetic [worked report](examples/envelope-report/report.json).

## Compare years on matching months (JSON CLI)

```sh
python -m energy_report.compare examples/synthetic_comparison.csv \
  --baseline-year 2024 --comparison-year 2025 --out comparison.json
```

Use the same validated CSV contract. For each site, only calendar months observed
in **both** selected years contribute to the comparison. This prevents a partial
year from being compared against a fuller year as though coverage were equal.
The output lists matched months, baseline-only months, comparison-only months,
and any other years excluded by the explicit selection. It includes an input
SHA-256 fingerprint and refuses to overwrite existing output files.

In the wholly synthetic fixture, the workshop's January changes from 100 to
80 kWh (**−20%**) while its cost changes from €20 to €24 (**+20%**). February
exists only in the baseline and March only in the comparison: neither contributes
to these totals. Comparing the raw 1,100 and 480 kWh totals would be misleading.
The sample result is [matched-comparison.json](examples/matched-comparison.json).

No common months produces `null` totals, **not zero**. A zero baseline produces
`null` percentage change with an absolute change still available. Sites present
in just one selected year remain visible. `full_calendar_year` is true only when
all twelve months match. Years need not be adjacent, but the comparison year must
be later; a multi-year change is **not annualized**. There is no cross-site total
because sites can have different matched calendars. This is a separate comparison
schema; the existing report JSON schemas are unchanged.

**Matching months is not weather or occupancy normalization.** Leap-year days,
actual billing intervals, changed meter scope and tariffs can still bias the
comparison. Input energy scope and tax basis must be consistent. Changes are not
verified savings, causal findings or a certified measurement-and-verification
result. Do not publish real input or output records.
