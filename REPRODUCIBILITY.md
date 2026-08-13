# Reproducibility

The repository separates frozen-evidence verification from full empirical reconstruction.

## Frozen-evidence verification

Install:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-ci.txt
python -m pip check
```

Run:

```bash
python -m scripts.research.verify_repository
```

The verifier checks:

- controlled file SHA-256 values;
- final assurance decision;
- all 16 required research checks;
- publication-evidence state;
- Apache-2.0 licence presence;
- absence of tracked raw market-data caches.

Expected result:

```text
REPOSITORY ASSURANCE: PASS
```

## Full empirical reconstruction

A full rerun requires reacquisition of third-party market data.

The research sequence is:

```bash
python -m scripts.research.source_capability_probe
python -m scripts.research.hourly_history
python -m scripts.research.hourly_dispersion_analysis
python -m scripts.research.extreme_gap_validation --top 40
python -m scripts.research.valuation_boundary_analysis
python -m scripts.research.volatility_dispersion_analysis
python -m scripts.research.final_assurance
python -m scripts.research.publication_figures
```

The pipeline is designed to fail closed.

No interpolation or forward filling is used to repair unavailable market observations.

## Daily boundaries

The controlled daily valuation conventions are:

- 00:00 UTC;
- 16:00 Europe/London;
- 16:00 America/New_York.

Local-clock boundaries use timezone-aware daylight-saving conversion.

## Prior volatility

The final RV24 sensitivity uses strict calendar time.

For dispersion observed at hour `t`, realized volatility uses the 24 calendar hours strictly preceding the current hour.

The current-hour return is excluded.

## Frozen evidence

Repository evidence is recorded in:

```text
evidence/repository_evidence.json
```

Changing a controlled file invalidates the frozen verification until the evidence registry is intentionally regenerated.
