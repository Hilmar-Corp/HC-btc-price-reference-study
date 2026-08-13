from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")

import matplotlib.pyplot as plt

OUTPUT_DIR = Path("artifacts/publication_figures")

DISPERSION_PERIOD_PATH = Path("artifacts/extreme_gap_validation/subperiod_summary.csv")

EXTREME_SUMMARY_PATH = Path("artifacts/extreme_gap_validation/validation_summary.json")

CUTOFF_PAIRWISE_PATH = Path("artifacts/valuation_boundary/cutoff_pairwise_summary.csv")

VENUE_EFFECT_PATH = Path("artifacts/valuation_boundary/venue_effect_summary.csv")

TOP_CUTOFF_PATH = Path("artifacts/valuation_boundary/largest_cutoff_effect_dates.csv")

STRICT_RV_PATH = Path("artifacts/final_assurance/strict_calendar_rv_validation.csv")

FINAL_DECISION_PATH = Path("artifacts/final_assurance/consolidated_decision.json")

FIGURE_1 = OUTPUT_DIR / "figure_01_venue_convergence.png"
FIGURE_1_SVG = OUTPUT_DIR / "figure_01_venue_convergence.svg"

FIGURE_2 = OUTPUT_DIR / "figure_02_extreme_gap_revalidation.png"
FIGURE_2_SVG = OUTPUT_DIR / "figure_02_extreme_gap_revalidation.svg"

FIGURE_3 = OUTPUT_DIR / "figure_03_same_date_different_returns.png"
FIGURE_3_SVG = OUTPUT_DIR / "figure_03_same_date_different_returns.svg"

FIGURE_4 = OUTPUT_DIR / "figure_04_cutoff_vs_venue_effect.png"
FIGURE_4_SVG = OUTPUT_DIR / "figure_04_cutoff_vs_venue_effect.svg"

FIGURE_5 = OUTPUT_DIR / "figure_05_volatility_dispersion_appendix.png"
FIGURE_5_SVG = OUTPUT_DIR / "figure_05_volatility_dispersion_appendix.svg"

SUMMARY_PATH = OUTPUT_DIR / "publication_figure_summary.json"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

DPI = 320

BLACK = "#111111"
DARK = "#444444"
MID = "#777777"
LIGHT = "#BBBBBB"
GRID = "#E6E6E6"


def format_bps(value: float) -> str:
    if abs(value) >= 100:
        return f"{value:.0f}"

    if abs(value) >= 10:
        return f"{value:.1f}"

    return f"{value:.2f}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise TypeError(f"{path} doit contenir un objet JSON.")

    return payload


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.titlesize": 10.5,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.edgecolor": BLACK,
            "axes.linewidth": 0.65,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def style_axis(axis: plt.Axes) -> None:
    axis.tick_params(
        axis="both",
        length=3,
        width=0.65,
        color=BLACK,
    )

    axis.spines["left"].set_color(BLACK)
    axis.spines["bottom"].set_color(BLACK)


def save(
    figure: plt.Figure,
    png: Path,
    svg: Path,
) -> None:
    figure.savefig(
        png,
        dpi=DPI,
        bbox_inches="tight",
        pad_inches=0.06,
    )

    figure.savefig(
        svg,
        bbox_inches="tight",
        pad_inches=0.06,
    )

    plt.close(figure)


def figure_venue_convergence(
    frame: pd.DataFrame,
) -> dict[str, Any]:
    x = np.arange(len(frame))

    figure, axis = plt.subplots(figsize=(6.8, 4.0))

    style_axis(axis)

    axis.plot(
        x,
        frame["p99_bps"],
        color=LIGHT,
        linewidth=1.0,
        marker="o",
        markersize=3.2,
        label="P99",
    )

    axis.plot(
        x,
        frame["p90_bps"],
        color=MID,
        linewidth=1.1,
        marker="o",
        markersize=3.4,
        label="P90",
    )

    axis.plot(
        x,
        frame["median_bps"],
        color=BLACK,
        linewidth=1.5,
        marker="o",
        markersize=3.8,
        label="Médiane",
    )

    axis.set_yscale("log")

    axis.set_xticks(x)
    axis.set_xticklabels(frame["subperiod"])

    axis.set_ylabel("Dispersion (bps, échelle log)")

    axis.set_title(
        "Figure 1. Dispersion horaire Coinbase-Bitstamp",
        loc="left",
        pad=8,
        fontweight="bold",
    )

    axis.grid(
        axis="y",
        which="major",
        color=GRID,
        linewidth=0.6,
    )

    axis.legend(
        frameon=False,
        loc="upper right",
        ncol=3,
        handlelength=1.6,
        columnspacing=1.0,
    )

    for index, value in enumerate(frame["median_bps"].to_numpy(dtype=float)):
        axis.annotate(
            format_bps(value),
            xy=(index, value),
            xytext=(0, -12),
            textcoords="offset points",
            ha="center",
            fontsize=7.3,
            color=BLACK,
        )

    figure.subplots_adjust(
        left=0.12,
        right=0.98,
        top=0.91,
        bottom=0.12,
    )

    save(
        figure,
        FIGURE_1,
        FIGURE_1_SVG,
    )

    return {
        "figure": "figure_01_venue_convergence",
        "recent_median_bps": float(frame.iloc[-1]["median_bps"]),
    }


def figure_extreme_revalidation(
    summary: dict[str, Any],
) -> dict[str, Any]:
    labels = [
        "Horaire\nCoinbase + Bitstamp",
        "Dernière minute\nCoinbase + Bitstamp",
        "Dernière minute\n+ Kraken",
    ]

    values = np.array(
        [
            float(summary["selected_hourly_dispersion_bps"]["median"]),
            float(summary["minute_two_source_dispersion_bps"]["median"]),
            float(summary["minute_three_source_dispersion_bps"]["median"]),
        ]
    )

    y = np.arange(len(labels))

    figure, axis = plt.subplots(figsize=(6.8, 3.5))

    style_axis(axis)

    axis.hlines(
        y=y,
        xmin=0,
        xmax=values,
        color=LIGHT,
        linewidth=1.0,
    )

    axis.scatter(
        values,
        y,
        s=32,
        color=BLACK,
        zorder=3,
    )

    axis.set_yticks(y)
    axis.set_yticklabels(labels)
    axis.invert_yaxis()

    axis.set_xlabel("Dispersion médiane (bps)")

    axis.set_xlim(
        0,
        max(values) * 1.16,
    )

    axis.set_title(
        "Figure 2. Revalidation des écarts horaires extrêmes",
        loc="left",
        pad=8,
        fontweight="bold",
    )

    axis.grid(
        axis="x",
        color=GRID,
        linewidth=0.6,
    )

    for index, value in enumerate(values):
        axis.text(
            value + max(values) * 0.025,
            index,
            f"{value:.1f}",
            va="center",
            fontsize=7.6,
            color=BLACK,
        )

    figure.subplots_adjust(
        left=0.25,
        right=0.98,
        top=0.89,
        bottom=0.15,
    )

    save(
        figure,
        FIGURE_2,
        FIGURE_2_SVG,
    )

    return {
        "figure": "figure_02_extreme_gap_revalidation",
        "hourly_median_bps": float(values[0]),
        "three_source_minute_median_bps": float(values[2]),
    }


def figure_same_date_returns(
    frame: pd.DataFrame,
) -> dict[str, Any]:
    row = frame.iloc[0]

    labels = [
        "00:00 UTC",
        "16:00 Londres",
        "16:00 New York",
    ]

    values = np.array(
        [
            float(row["composite_return__utc_0000"]) * 100.0,
            float(row["composite_return__london_1600"]) * 100.0,
            float(row["composite_return__new_york_1600"]) * 100.0,
        ]
    )

    y = np.arange(len(labels))

    figure, axis = plt.subplots(figsize=(6.8, 3.5))

    style_axis(axis)

    axis.axvline(
        0,
        color=BLACK,
        linewidth=0.7,
    )

    for index, value in enumerate(values):
        axis.hlines(
            y=index,
            xmin=min(
                value,
                0.0,
            ),
            xmax=max(
                value,
                0.0,
            ),
            color=DARK,
            linewidth=2.4,
        )

        axis.scatter(
            value,
            index,
            color=BLACK,
            s=28,
            zorder=3,
        )

    axis.set_yticks(y)
    axis.set_yticklabels(labels)
    axis.invert_yaxis()

    axis.set_xlabel("Rendement journalier (%)")

    axis.set_title(
        f"Figure 3. Rendement selon l'heure de valorisation - {row['date']}",
        loc="left",
        pad=8,
        fontweight="bold",
    )

    axis.grid(
        axis="x",
        color=GRID,
        linewidth=0.6,
    )

    span = max(
        abs(values.min()),
        abs(values.max()),
    )

    left_margin = span * 0.055
    right_margin = span * 0.080

    axis.set_xlim(
        values.min() - left_margin,
        values.max() + right_margin,
    )

    for index, value in enumerate(values):
        if value < 0:
            xytext = (10, 9)
            vertical_alignment = "bottom"
        else:
            xytext = (10, 0)
            vertical_alignment = "center"

        axis.annotate(
            f"{value:+.2f} %",
            xy=(value, index),
            xytext=xytext,
            textcoords="offset points",
            ha="left",
            va=vertical_alignment,
            fontsize=7.6,
            color=BLACK,
        )

    figure.subplots_adjust(
        left=0.20,
        right=0.98,
        top=0.89,
        bottom=0.15,
    )

    save(
        figure,
        FIGURE_3,
        FIGURE_3_SVG,
    )

    return {
        "figure": "figure_03_same_date_different_returns",
        "date": str(row["date"]),
        "utc_pct": float(values[0]),
        "london_pct": float(values[1]),
        "new_york_pct": float(values[2]),
    }


def figure_cutoff_vs_venue(
    venue: pd.DataFrame,
    cutoff: pd.DataFrame,
) -> dict[str, Any]:
    venue_labels = {
        "utc_0000": "Plateforme | 00:00 UTC",
        "london_1600": "Plateforme | 16:00 Londres",
        "new_york_1600": "Plateforme | 16:00 New York",
    }

    cutoff_labels = {
        "UTC 00:00 vs London 16:00": "Heure | UTC / Londres",
        "UTC 00:00 vs New York 16:00": "Heure | UTC / New York",
        "London 16:00 vs New York 16:00": "Heure | Londres / New York",
    }

    rows: list[dict[str, Any]] = []

    for _, row in venue.iterrows():
        rows.append(
            {
                "label": venue_labels[str(row["convention"])],
                "group": "plateforme",
                "median": float(row["median"]),
                "p90": float(row["p90"]),
            }
        )

    for _, row in cutoff.iterrows():
        rows.append(
            {
                "label": cutoff_labels[str(row["comparison"])],
                "group": "heure",
                "median": float(row["median"]),
                "p90": float(row["p90"]),
            }
        )

    frame = pd.DataFrame(rows)

    y = np.array(
        [
            0,
            1,
            2,
            4,
            5,
            6,
        ]
    )

    figure, axis = plt.subplots(figsize=(7.0, 4.2))

    style_axis(axis)

    for position, (_, row) in zip(
        y,
        frame.iterrows(),
        strict=True,
    ):
        color = MID if row["group"] == "plateforme" else BLACK

        axis.hlines(
            y=position,
            xmin=row["median"],
            xmax=row["p90"],
            color=color,
            linewidth=1.5,
        )

        axis.scatter(
            row["median"],
            position,
            s=30,
            color=color,
            zorder=3,
        )

        axis.scatter(
            row["p90"],
            position,
            s=26,
            facecolor="white",
            edgecolor=color,
            linewidth=0.9,
            zorder=3,
        )

        axis.text(
            row["median"] * 1.08,
            position - 0.18,
            format_bps(row["median"]),
            fontsize=7.2,
            color=color,
        )

    axis.set_xscale("log")

    axis.set_yticks(y)
    axis.set_yticklabels(frame["label"])

    axis.invert_yaxis()

    axis.set_xlabel("Écart absolu de rendement (bps, échelle log)")

    axis.set_title(
        "Figure 4. Effet plateforme et effet heure de valorisation",
        loc="left",
        pad=8,
        fontweight="bold",
    )

    axis.grid(
        axis="x",
        which="major",
        color=GRID,
        linewidth=0.6,
    )

    axis.axhline(
        3,
        color=LIGHT,
        linewidth=0.6,
    )

    axis.text(
        0.99,
        0.97,
        "● Médiane    ○ P90",
        transform=axis.transAxes,
        ha="right",
        va="top",
        fontsize=7.1,
        color=MID,
    )

    figure.subplots_adjust(
        left=0.31,
        right=0.98,
        top=0.90,
        bottom=0.14,
    )

    save(
        figure,
        FIGURE_4,
        FIGURE_4_SVG,
    )

    return {
        "figure": "figure_04_cutoff_vs_venue_effect",
        "venue_median_min_bps": float(venue["median"].min()),
        "venue_median_max_bps": float(venue["median"].max()),
        "cutoff_median_min_bps": float(cutoff["median"].min()),
        "cutoff_median_max_bps": float(cutoff["median"].max()),
    }


def figure_volatility_appendix(
    frame: pd.DataFrame,
) -> dict[str, Any]:
    full = frame.loc[frame["sample"] == "full_sample"].iloc[0]

    recent = frame.loc[frame["sample"] == "2024-2026"].iloc[0]

    x = np.arange(
        1,
        6,
    )

    full_values = np.array([float(full[f"q{i}_median_dispersion_bps"]) for i in x])

    recent_values = np.array([float(recent[f"q{i}_median_dispersion_bps"]) for i in x])

    figure, axis = plt.subplots(figsize=(6.8, 3.7))

    style_axis(axis)

    axis.plot(
        x,
        full_values,
        color=MID,
        linewidth=1.1,
        marker="o",
        markersize=3.2,
        label="2017-2026",
    )

    axis.plot(
        x,
        recent_values,
        color=BLACK,
        linewidth=1.5,
        marker="o",
        markersize=3.6,
        label="2024-2026",
    )

    axis.set_xticks(x)
    axis.set_xticklabels(
        [
            "Q1",
            "Q2",
            "Q3",
            "Q4",
            "Q5",
        ]
    )

    axis.set_xlabel("Quintile de volatilité réalisée sur les 24 h précédentes")

    axis.set_ylabel("Dispersion médiane (bps)")

    axis.set_title(
        "Annexe. Dispersion conditionnelle à la volatilité passée",
        loc="left",
        pad=8,
        fontweight="bold",
    )

    axis.grid(
        axis="y",
        color=GRID,
        linewidth=0.6,
    )

    axis.legend(
        frameon=False,
        loc="upper left",
    )

    figure.subplots_adjust(
        left=0.12,
        right=0.98,
        top=0.89,
        bottom=0.15,
    )

    save(
        figure,
        FIGURE_5,
        FIGURE_5_SVG,
    )

    return {
        "figure": "figure_05_volatility_dispersion_appendix",
        "full_q5_q1": float(full_values[-1] / full_values[0]),
        "recent_q5_q1": float(recent_values[-1] / recent_values[0]),
    }


def main() -> None:
    configure_style()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    decision = read_json(FINAL_DECISION_PATH)

    if decision.get("decision") != "PASS":
        raise RuntimeError("Le contrôle final doit être PASS.")

    period = pd.read_csv(DISPERSION_PERIOD_PATH)

    extreme = read_json(EXTREME_SUMMARY_PATH)

    cutoff = pd.read_csv(CUTOFF_PAIRWISE_PATH)

    venue = pd.read_csv(VENUE_EFFECT_PATH)

    top_cutoff = pd.read_csv(TOP_CUTOFF_PATH)

    strict_rv = pd.read_csv(STRICT_RV_PATH)

    figures = [
        figure_venue_convergence(period),
        figure_extreme_revalidation(extreme),
        figure_same_date_returns(top_cutoff),
        figure_cutoff_vs_venue(
            venue,
            cutoff,
        ),
        figure_volatility_appendix(strict_rv),
    ]

    outputs = [
        FIGURE_1,
        FIGURE_1_SVG,
        FIGURE_2,
        FIGURE_2_SVG,
        FIGURE_3,
        FIGURE_3_SVG,
        FIGURE_4,
        FIGURE_4_SVG,
        FIGURE_5,
        FIGURE_5_SVG,
    ]

    summary_core = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "stage": ("PUBLICATION_FIGURES"),
        "final_assurance": (decision["decision"]),
        "figures": figures,
    }

    summary = {
        **summary_core,
        "generated_at_utc": (datetime.now(UTC).isoformat()),
        "summary_sha256": (canonical_sha256(summary_core)),
    }

    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manifest = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "stage": ("PUBLICATION_FIGURES"),
        "artifacts": [
            {
                "path": str(path),
                "sha256": (sha256_file(path)),
                "size_bytes": (path.stat().st_size),
            }
            for path in outputs
        ],
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    for path in outputs:
        if not path.is_file():
            raise RuntimeError(f"Figure absente : {path}")

        if path.stat().st_size < 1000:
            raise RuntimeError(f"Figure anormalement petite : {path}")

    print()
    print("HILMARCORP BTC PRICE REFERENCE")
    print("FIGURES DE PUBLICATION")
    print("=" * 72)

    for path in outputs:
        print(
            path,
            f"{path.stat().st_size / 1024:.1f} KB",
        )

    print()
    print("PUBLICATION FIGURE GATE: PASS")


if __name__ == "__main__":
    main()
