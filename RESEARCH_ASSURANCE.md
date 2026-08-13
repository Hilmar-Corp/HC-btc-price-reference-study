# Research Assurance

## Objective

The assurance layer is designed to ensure that published analytical conclusions remain traceable to controlled data transformations, deterministic tests and versioned evidence.

## Final decision

The current frozen research bundle records:

```text
FINAL RESEARCH ASSURANCE: PASS
16 / 16 required controls passed
```

The canonical decision artifact is:

```text
artifacts/final_assurance/consolidated_decision.json
```

## Control domains

The consolidated gate covers:

1. historical source capability;
2. recent source capability;
3. Coinbase hourly coverage;
4. Bitstamp hourly coverage;
5. common-hour sample size;
6. dispersion-panel consistency;
7. three-source extreme-event revalidation;
8. extreme-gap persistence at one-minute resolution;
9. valuation-boundary sample size;
10. missing-boundary control;
11. DST sensitivity;
12. strict-calendar full-sample RV24 sensitivity;
13. strict-calendar recent RV24 sensitivity;
14. full-sample volatility-quintile monotonicity;
15. recent volatility-quintile monotonicity;
16. controlled artifact presence.

## Fail-closed principle

A required failed check results in:

```text
FINAL RESEARCH ASSURANCE: FAIL
```

No required check is silently ignored.

## Analytical-core coverage

GitHub Actions separately enforces:

```text
line coverage >= 85%
branch coverage >= 75%
```

for the controlled analytical core.

## Evidence integrity

Controlled evidence uses SHA-256 manifests.

Repository-level frozen hashes are stored in:

```text
evidence/repository_evidence.json
```

## Raw data

Complete raw market-data caches are deliberately outside the public Git history.

This prevents the repository software licence from being confused with third-party data rights.
