"""Compare observed sites with an explicit register, without imputing readings."""
from .report import DataError


def add_site_register(result, expected_sites):
    """Add a versioned, additive register check to a report in place.

    Names match case-sensitively after trimming outer whitespace, just like CSV
    site names. Unlisted observations remain in the report, never filtered out.
    """
    if isinstance(expected_sites, (str, bytes)) or not expected_sites:
        raise DataError('Expected sites must be a nonempty list of names')
    names = []
    for site in expected_sites:
        if not isinstance(site, str) or not site.strip():
            raise DataError('Expected site names must be nonblank strings')
        names.append(site.strip())
    if len(names) != len(set(names)):
        raise DataError('Duplicate expected site names after trimming whitespace')
    if 'site_register' in result:
        raise DataError('A site register has already been applied')
    observed = {site['site'] for site in result['sites']}
    expected = set(names)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    result['site_register'] = {
        'schema_version': 1,
        'expected_sites': sorted(expected),
        'missing_sites': missing,
        'unexpected_sites': unexpected,
        'observed_expected_sites': sorted(expected & observed),
        'basis': 'Presence of at least one reading in the input, not full-period completeness',
    }
    for site in missing:
        result['warnings'].append(f'{site}: expected site has no readings; consumption is unknown, not zero')
    for site in unexpected:
        result['warnings'].append(f'{site}: observed site is absent from the declared register; readings retained')
    return result
