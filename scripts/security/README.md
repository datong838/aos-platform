# Sensitive data scanner

This directory contains a read-only pre-commit and delivery-staging scanner.
It never prints or hashes a matched credential; findings contain only the
rule, path, line, severity, and a short SHA-256 location fingerprint.

## Commands

Scan Git-tracked files:

```bash
python3 scripts/security/scan_sensitive.py
```

CI-friendly summary while preserving the same scan coverage:

```bash
python3 scripts/security/scan_sensitive.py --report summary
```

Scan an explicit delivery staging directory and fail on PII warnings:

```bash
python3 scripts/security/scan_sensitive.py --fail-on-warning /path/to/staging
```

Run the isolated tests:

```bash
cd scripts/security
python3 -m unittest -v test_scan_sensitive.py
```

## Exit codes

- `0`: no critical finding; warnings are informational unless strict mode is on.
- `1`: a critical finding, or a warning under `--fail-on-warning`.
- `2`: invalid configuration or scanner execution error.

## Allowlist

An allowlist is a JSON array. Every entry must contain an exact `rule`, `path`,
and a non-empty `reason`. Broad directory or global suppressions are not
supported. The repository default is `scripts/security/allowlist.json`.

```json
[
  {
    "rule": "GENERIC_SECRET",
    "path": "tests/fixtures/synthetic.txt",
    "reason": "synthetic negative fixture"
  }
]
```

Do not place real credentials or personal data in negative fixtures. Construct
synthetic, invalid values inside the test instead.
