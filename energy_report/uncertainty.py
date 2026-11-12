"""Deterministic scenario envelopes, not probabilistic confidence intervals."""
from decimal import Decimal
from .report import DataError


def emission_envelope(observed_kwh, factor_low, factor_high, meter_error_percent=Decimal('0')):
    """Propagate nonnegative factor bounds and symmetric relative energy error.

    Bounds assume all error extremes may coincide (including systematic meter bias).
    They apply only to observed energy; missing months remain outside the estimate.
    """
    values = (observed_kwh, factor_low, factor_high, meter_error_percent)
    if any(not isinstance(value, Decimal) or not value.is_finite() or value < 0 for value in values):
        raise DataError('Envelope inputs must be finite nonnegative Decimals')
    if factor_low > factor_high:
        raise DataError('Factor lower bound must not exceed upper bound')
    if meter_error_percent > 100:
        raise DataError('Meter error must be between 0 and 100 percent')
    relative = meter_error_percent / 100
    low_energy = observed_kwh * (1 - relative)
    high_energy = observed_kwh * (1 + relative)
    return {
        'method': 'deterministic corner envelope; not a confidence interval',
        'scope': 'observed consumption only; no missing-month imputation',
        'energy_low_kwh': str(low_energy), 'energy_high_kwh': str(high_energy),
        'emissions_low_kgco2e': str(low_energy * factor_low),
        'emissions_high_kgco2e': str(high_energy * factor_high),
        'factor_low_kgco2e_per_kwh': str(factor_low),
        'factor_high_kgco2e_per_kwh': str(factor_high),
        'meter_error_percent': str(meter_error_percent),
        # One-at-a-time widths expose which assumption drives the range.
        'factor_only_width_kgco2e': str(observed_kwh * (factor_high - factor_low)),
        'meter_only_width_at_mid_factor_kgco2e': str(observed_kwh * relative * (factor_low + factor_high)),
    }


def add_envelopes(report, factor_low, factor_high, meter_error_percent=Decimal('0')):
    """Enrich a report in place without changing observed totals or central estimates."""
    envelopes = [emission_envelope(Decimal(site['kwh']), factor_low, factor_high, meter_error_percent)
                 for site in report['sites']]
    for site, envelope in zip(report['sites'], envelopes):
        site['emission_envelope'] = envelope
    report['schema_version'] = 3
    report['limitations'].append('Scenario envelope bounds are user assumptions, not a statistical uncertainty estimate; missing months are excluded.')
    return report
