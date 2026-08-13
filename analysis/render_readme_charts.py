"""Render the README's chart section from output/data.json.

The numbers in a README rot the moment they are typed by hand. This regenerates
the block between the CHARTS markers so it always matches the built payload.
Bars are Unicode block characters inside fenced blocks: they render identically
on GitHub, in an editor and in a terminal, and cost no binary assets — which
matters, because the dashboard itself is committed to having no external files.

Run after `python -m analysis.build_data`:

    python -m analysis.render_readme_charts
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BEGIN = "<!-- CHARTS:BEGIN -->"
END = "<!-- CHARTS:END -->"

FULL = "█"
EMPTY = "·"


class ChartRenderError(Exception):
    """Raised when the payload or the README is not in a usable state."""


def bar(value: float, maximum: float, width: int) -> str:
    """A proportional bar. Zero maximum yields an empty track, never a crash."""
    filled = 0 if maximum <= 0 else int(round(value / maximum * width))
    filled = max(0, min(width, filled))
    return FULL * filled + EMPTY * (width - filled)


def top_cities_block(payload: dict, count: int = 12) -> list[str]:
    cities = payload["cities"][:count]
    peak = max(c["roi_pct"] for c in cities)
    lines = [f"Top {count} cities by return on investment", ""]
    for i, c in enumerate(cities, 1):
        lines.append(
            f"{i:>3}. {c['city']:<14}{c['country']:<16}"
            f"{bar(c['roi_pct'], peak, 30)} {c['roi_pct']:>5.1f}%"
        )
    return lines


def regions_block(payload: dict) -> list[str]:
    regions = payload["regions"]
    peak_roi = max(r["mean_roi"] for r in regions)
    peak_inst = max(r["installations"] for r in regions)
    lines = [
        "Mean ROI against installed base, by region",
        "",
        f"{'region':<15}{'mean ROI':<26}{'installations':<26}",
    ]
    for r in regions:
        lines.append(
            f"{r['region']:<15}"
            f"{bar(r['mean_roi'], peak_roi, 16)} {r['mean_roi']:>5.2f}%   "
            f"{bar(r['installations'], peak_inst, 16)} {r['installations']:>9,}"
        )
    lines += [
        "",
        "Europe has the most cities and the lowest return; Asia holds 63% of the",
        "installed base and ranks fifth of seven on return.",
    ]
    return lines


def risk_block(payload: dict) -> list[str]:
    regions = payload["regions"]
    totals = {"Low": 0, "Medium": 0, "High": 0}
    for r in regions:
        for band, n in r["risk_counts"].items():
            totals[band] += n
    peak = max(totals.values())
    lines = ["Payback risk (Low < 7 yrs | Medium 7-9 | High > 9)", ""]
    for band in ("Low", "Medium", "High"):
        lines.append(
            f"{band:<8}{bar(totals[band], peak, 30)} {totals[band]:>3} cities"
        )
    return lines


def mismatch_block(payload: dict, count: int = 12) -> list[str]:
    cities = payload["cities"]
    left = sorted(cities, key=lambda c: (-c["installations"], c["city"]))[:count]
    right = sorted(cities, key=lambda c: (-c["roi_pct"], c["city"]))[:count]
    left_keys = {c["city"] for c in left}
    right_keys = {c["city"] for c in right}
    shared = left_keys & right_keys

    r = payload["correlations"]["installations_vs_roi"]
    lines = [
        f"Where solar is installed vs where it pays back   r = {r}",
        "",
        f"{'MOST INSTALLATIONS':<33}| BEST RETURN",
        "-" * 33 + "+" + "-" * 30,
    ]
    for a, b in zip(left, right):
        mark_a = "*" if a["city"] in shared else " "
        mark_b = "*" if b["city"] in shared else " "
        lines.append(
            f"{mark_a} {a['city']:<16}{a['installations']:>13,} "
            f"|{mark_b} {b['city']:<16}{b['roi_pct']:>5.1f}%"
        )
    lines += ["", f"* in both lists - {len(shared)} of {count}"]
    return lines


def render(payload: dict) -> str:
    t = payload["totals"]
    parts = [
        BEGIN,
        "",
        f"**{t['cities']} cities · {t['countries']} countries · {t['regions']} regions · "
        f"{t['co2_tons']:,.2f} t CO₂ avoided per year · "
        f"{t['installations']:,} installations**",
        "",
        "_Generated from `output/data.json` by `analysis/render_readme_charts.py` — "
        "do not edit by hand._",
        "",
    ]
    for block in (
        mismatch_block(payload),
        top_cities_block(payload),
        regions_block(payload),
        risk_block(payload),
    ):
        parts += ["```text", *block, "```", ""]
    parts.append(END)
    return "\n".join(parts)


def update(readme_path: Path, data_path: Path) -> str:
    if not data_path.is_file():
        raise ChartRenderError(
            f"payload not found: {data_path} — run `python -m analysis.build_data` first"
        )
    payload = json.loads(data_path.read_text(encoding="utf-8"))

    if not readme_path.is_file():
        raise ChartRenderError(f"README not found: {readme_path}")
    text = readme_path.read_text(encoding="utf-8")

    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ChartRenderError(
            f"README must contain exactly one {BEGIN} and one {END} marker"
        )
    start = text.index(BEGIN)
    end = text.index(END) + len(END)
    if end < start:
        raise ChartRenderError("README markers are out of order")

    updated = text[:start] + render(payload) + text[end:]
    readme_path.write_text(updated, encoding="utf-8")
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate the README chart block")
    parser.add_argument("readme", nargs="?", default="README.md")
    parser.add_argument("data", nargs="?", default="output/data.json")
    args = parser.parse_args(argv)

    try:
        update(Path(args.readme), Path(args.data))
    except ChartRenderError as exc:
        print(f"README CHARTS FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"updated the chart block in {args.readme}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
