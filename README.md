# Bitcoin Price Reference Study

[![Research Assurance](https://github.com/Hilmar-Corp/HC-btc-price-reference-study/actions/workflows/research-assurance.yml/badge.svg?branch=main)](https://github.com/Hilmar-Corp/HC-btc-price-reference-study/actions/workflows/research-assurance.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![Research](https://img.shields.io/badge/research-multi--source-2ea44f)
![Assurance](https://img.shields.io/badge/assurance-fail--closed-2ea44f)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

**Reproducible multi-venue research package for Bitcoin price dispersion, valuation boundaries and reference-price construction.**

This repository contains the empirical pipeline, controlled research artifacts, validation framework and publication figures supporting a HilmarCorp Research note on Bitcoin price-reference construction.

The repository is intended as a reproducible quantitative-research package rather than as a standalone editorial publication.

## Research question

Bitcoin trades continuously across multiple venues and does not have a universal closing auction or globally imposed end-of-day boundary.

The study separates two measurement problems:

1. **Source effect** — how much do observed BTC/USD prices differ across venues at a common time?
2. **Valuation-boundary effect** — how much does a measured daily return change when the daily valuation boundary changes?

The study does not attempt to identify a unique or metaphysically "true" Bitcoin price.

It evaluates how an observable reference depends on explicit choices of:

- market venue;
- timestamp;
- time zone;
- aggregation rule;
- missing-data policy;
- validation convention.

## Research scope

Primary study period:

    2017-08-17 to 2026-08-10

Primary venues:

    Coinbase BTC-USD
    Bitstamp BTC/USD

Independent third source used for selected extreme-event validation:

    Kraken BTC/USD

Primary frequency:

    hourly

Daily valuation conventions:

    00:00 UTC
    16:00 Europe/London
    16:00 America/New_York

London and New York boundaries are implemented using IANA time zones and daylight-saving-aware conversion.

## Research design

For venue prices P(i,t), the cross-venue research reference is:

    M(t) = median(P(1,t), ..., P(N,t))

Cross-venue dispersion is measured in basis points relative to that reference:

    D(t) = 10,000 × [max(P(i,t)) - min(P(i,t))] / M(t)

For valuation boundary τ, the corresponding daily return is:

    r(t,τ) = P(t,τ) / P(t-1,τ) - 1

This design keeps two effects analytically separate:

- venue variation at a fixed valuation boundary;
- valuation-boundary variation under a fixed reference construction.

The research composite is an analytical construction used for this study.

It is not represented as an official benchmark or investable index.

## Data handling policy

The empirical pipeline applies the following controls:

- UTC-normalized timestamps;
- explicit source identities;
- no interpolation;
- no forward filling;
- no silent source substitution;
- deterministic exclusions;
- duplicate-timestamp checks;
- finite-value checks;
- positive-price checks;
- exact or explicitly bounded observation windows;
- DST-aware local-time conversion;
- strict backward information ordering;
- explicit missing-observation treatment;
- independent third-source validation for selected extreme events.

Missing market observations are not synthetically reconstructed.

## Research modules

### Source capability audit

Validates whether each source can support the historical and recent observation requirements defined by the research contract.

Primary outputs:

    artifacts/source_audit/

### Full hourly history

Constructs the controlled Coinbase / Bitstamp hourly history over the study period.

Primary outputs:

    artifacts/full_history_hourly/

### Cross-venue dispersion

Measures hourly price dispersion across common Coinbase / Bitstamp observations.

Primary outputs:

    artifacts/hourly_dispersion/

### Extreme-event revalidation

Selects the largest historical hourly gaps for diagnostic revalidation.

The final minute of each selected hour is re-examined and Kraken BTC/USD is introduced as an independent third source where available.

Primary outputs:

    artifacts/extreme_gap_validation/

### Valuation-boundary sensitivity

Measures daily returns under three valuation conventions:

    00:00 UTC
    16:00 Europe/London
    16:00 America/New_York

The module distinguishes venue effects at fixed time from boundary effects under a common reference construction.

Primary outputs:

    artifacts/valuation_boundary/

### Volatility and dispersion

Evaluates the descriptive association between cross-venue dispersion and realized volatility measured over the strictly preceding 24 calendar hours.

The return ending in the current observation hour is excluded from the volatility estimate.

Primary outputs:

    artifacts/volatility_dispersion/

### Final consolidated assurance

Combines the required research controls into a fail-closed final decision.

Primary outputs:

    artifacts/final_assurance/

## Published research snapshot

Primary hourly panel:

| Item | Value |
|---|---:|
| Expected hourly observations | 78,744 |
| Coinbase observations | 78,699 |
| Coinbase coverage | 99.943% |
| Bitstamp observations | 78,744 |
| Bitstamp coverage | 100.000% |
| Common hourly observations | 78,699 |

Final consolidated assurance:

| Item | Value |
|---|---:|
| Required checks | 16 |
| Passed checks | 16 |
| Failed checks | 0 |
| Decision | **PASS** |

Controlled analytical-core coverage at publication:

| Measure | Coverage |
|---|---:|
| Line coverage | 97.94% |
| Branch coverage | 94.44% |

CI minimums are lower than the frozen publication values:

    line coverage >= 85%
    branch coverage >= 75%

## Publication figures

Publication figures are generated from controlled analytical artifacts rather than manually entered numbers.

They are stored in:

    artifacts/publication_figures/

The current publication pack contains:

    figure_01_venue_convergence.png
    figure_02_extreme_gap_revalidation.png
    figure_03_same_date_different_returns.png
    figure_04_cutoff_vs_venue_effect.png
    figure_05_volatility_dispersion_appendix.png

SVG equivalents are provided for vector use.

The figure labels are in French because the current figures accompany a French-language HilmarCorp Research note.

## Research assurance

The repository uses a fail-closed assurance model.

The canonical consolidated decision is:

    artifacts/final_assurance/consolidated_decision.json

The current frozen bundle records:

    FINAL RESEARCH ASSURANCE: PASS
    16 / 16 required checks passed

Control domains include:

- historical source capability;
- recent source capability;
- Coinbase hourly coverage;
- Bitstamp hourly coverage;
- common-sample integrity;
- dispersion-panel consistency;
- three-source extreme-event revalidation;
- minute-level persistence of selected extreme gaps;
- valuation-boundary coverage;
- missing-boundary controls;
- DST sensitivity;
- strict-calendar RV24 validation;
- volatility-quintile monotonicity;
- controlled artifact presence.

A failed required control prevents a passing final decision.

Detailed documentation:

    RESEARCH_ASSURANCE.md

## Frozen evidence

Repository-level evidence is frozen in:

    evidence/repository_evidence.json

The registry records SHA-256 hashes for controlled:

- source code;
- tests;
- configuration;
- documentation;
- analytical artifacts;
- publication figures;
- assurance outputs.

A modification to a controlled file invalidates the frozen snapshot until the evidence registry is intentionally regenerated.

Verify the current snapshot with:

    python -m scripts.research.verify_repository

Expected result:

    REPOSITORY ASSURANCE: PASS

## Repository structure

    .
    ├── .github/
    │   └── workflows/
    │       └── research-assurance.yml
    ├── artifacts/
    │   ├── extreme_gap_validation/
    │   ├── final_assurance/
    │   ├── full_history_hourly/
    │   ├── gate3_validation/
    │   ├── hourly_dispersion/
    │   ├── publication_figures/
    │   ├── source_audit/
    │   ├── valuation_boundary/
    │   └── volatility_dispersion/
    ├── evidence/
    │   └── repository_evidence.json
    ├── scripts/
    │   └── research/
    ├── tests/
    ├── acquisition_protocol.json
    ├── research_contract.json
    ├── source_registry.json
    ├── DATA_NOTICE.md
    ├── REPRODUCIBILITY.md
    ├── RESEARCH_ASSURANCE.md
    ├── CITATION.cff
    ├── LICENSE
    ├── NOTICE
    ├── Makefile
    ├── pyproject.toml
    └── requirements-ci.txt

## Installation

Controlled runtime:

    Python 3.12

Create an isolated environment:

    python3.12 -m venv .venv
    source .venv/bin/activate

Install controlled dependencies:

    python -m pip install --upgrade pip
    python -m pip install -r requirements-ci.txt
    python -m pip check

## Static assurance

Run formatting validation:

    python -m ruff format --check scripts tests

Run linting:

    python -m ruff check scripts tests

Run compilation:

    python -m compileall -q scripts tests

## Tests

Run the complete deterministic test suite:

    python -m pytest -q

## Analytical-core coverage

Run:

    make coverage

Expected result:

    CORE COVERAGE GATE: PASS

The CI thresholds are:

    line coverage >= 85%
    branch coverage >= 75%

## Complete local assurance

Run:

    make assurance

This executes:

1. Ruff format validation.
2. Ruff linting.
3. Python compilation.
4. Complete deterministic tests.
5. Frozen repository-evidence verification.
6. Analytical-core line and branch coverage gates.

A valid publication state must finish with:

    REPOSITORY ASSURANCE: PASS
    CORE COVERAGE GATE: PASS

## Full empirical reconstruction

A full empirical rerun requires reacquisition of third-party market data.

The intended sequence is:

    python -m scripts.research.source_capability_probe
    python -m scripts.research.hourly_history
    python -m scripts.research.hourly_dispersion_analysis
    python -m scripts.research.extreme_gap_validation --top 40
    python -m scripts.research.valuation_boundary_analysis
    python -m scripts.research.volatility_dispersion_analysis
    python -m scripts.research.final_assurance
    python -m scripts.research.publication_figures

See:

    REPRODUCIBILITY.md

for the detailed reconstruction protocol.

## GitHub Research Assurance

Every push to `main`, pull request and manual workflow dispatch runs the repository Research Assurance workflow.

The workflow validates:

- controlled dependency installation;
- Ruff formatting;
- Ruff linting;
- Python compilation;
- deterministic test execution;
- frozen SHA-256 evidence;
- the consolidated 16/16 research decision;
- absence of tracked raw market-data caches;
- analytical-core line coverage;
- analytical-core branch coverage.

Generated CI assurance evidence is uploaded as a GitHub Actions artifact.

## Data provenance and third-party rights

Complete third-party raw market-data caches are intentionally excluded from the public Git history.

The repository supports two distinct forms of reproducibility:

1. **Frozen-output verification** — exact validation of committed code, derived artifacts, figures and SHA-256 evidence.
2. **Methodological reconstruction** — reacquisition of source data followed by rerunning the documented empirical pipeline.

Third-party market data remains subject to the rights, terms and restrictions of the relevant providers.

The Apache License 2.0 applies to HilmarCorp's original repository content as described in `LICENSE` and `NOTICE`.

It does not grant rights to third-party exchange datasets, services or trademarks.

See:

    DATA_NOTICE.md

## Interpretation limits

This repository contains descriptive empirical research.

It does not establish:

- a unique true Bitcoin price;
- an official Bitcoin benchmark;
- causal fragmentation effects;
- predictive power;
- future return forecasts;
- trading profitability;
- an optimal execution venue;
- an investment strategy.

The results remain conditional on:

- the selected venues;
- the study period;
- the available observations;
- the defined time boundaries;
- the aggregation conventions;
- the methodological controls documented in the repository.

Statistical significance, where reported, must not be interpreted as economic predictability.

## Research governance

The repository is designed to preserve:

- reproducibility;
- source traceability;
- explicit methodological conventions;
- controlled exclusions;
- deterministic testing;
- multi-source validation;
- evidence integrity;
- versioned analytical outputs;
- fail-closed assurance;
- resistance to unsupported editorial claims.

The repository does not claim certification or endorsement by any external asset manager, hedge fund, benchmark administrator or quantitative investment firm.

## Citation

Citation metadata is provided in:

    CITATION.cff

## License

Original HilmarCorp code, tests, automation and documentation are released under the Apache License 2.0.

See:

    LICENSE
    NOTICE

Third-party market data is outside the Apache-2.0 grant.

## Disclaimer

This repository is provided for quantitative research and educational purposes.

Nothing in this repository constitutes investment advice, a recommendation, a forecast, investment management, order execution, a solicitation, or an offer to buy or sell a financial instrument or digital asset.

Historical observations are not indicative of future outcomes.
