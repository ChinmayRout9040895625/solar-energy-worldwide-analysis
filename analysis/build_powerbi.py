"""Generate a Power BI Desktop project (PBIP) from output/data.json.

Format choice: TMSL (`model.bim`) for the semantic model and **PBIR** — the
`definition/` folder — for the report.

The first attempt emitted PBIR-Legacy (`report.json`) on the theory that an
older Desktop reads it natively. It opened to a blank canvas, because
Microsoft documents that file as one that "doesn't support external editing":
Desktop parses the project, takes the name, and discards a layout it did not
write itself. PBIR is the format built for external authoring — every file
carries a public JSON schema, and Desktop validates them on open and reports
which file is at fault. That is worth more than avoiding a preview toggle.

PBIR is a preview feature: enable **Store reports using enhanced metadata
format (PBIR)** under File > Options and settings > Options > Preview features
before opening the project.

The data is embedded in the model as a literal M `#table`, not read from the
CSV. A file path inside a Power BI query is absolute, so a generated project
that pointed at this machine's CSV would break the moment it moved. Embedding
48 rows costs a few KB and makes the project open anywhere — the same
self-containment rule the HTML dashboard follows.

DAX here mirrors analysis/metrics.py. Nothing executes DAX at build time, so
these expressions are translations, not verified computations; the expected
figures are printed on build so they can be checked against the report.

Run after `python -m analysis.build_data`:

    python -m analysis.build_powerbi
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path

NAME = "SolarEnergyWorldwide"
REQUIRED_KEYS = ("totals", "correlations", "cities", "regions", "countries")

CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720

# Source columns, in CSV order, with their M type and Tabular dataType.
COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("City", "text", "string"),
    ("Country", "text", "string"),
    ("Latitude", "number", "double"),
    ("Longitude", "number", "double"),
    ("Annual_Sunlight_Hours", "Int64.Type", "int64"),
    ("Daily_Peak_Sun_Hours", "number", "double"),
    ("GHI_kWh_per_m2", "number", "double"),
    ("Electricity_Price_USD_per_kWh", "number", "double"),
    ("Solar_Installations_Count", "Int64.Type", "int64"),
    ("Avg_System_Cost_USD", "number", "double"),
    ("Avg_Annual_Production_kWh", "Int64.Type", "int64"),
    ("Estimated_Annual_Savings_USD", "number", "double"),
    ("Payback_Period_Years", "number", "double"),
    ("ROI_Percentage", "number", "double"),
    ("CO2_Reduction_Tons_per_Year", "number", "double"),
    ("Solar_Viability_Score", "Int64.Type", "int64"),
    ("Region", "text", "string"),
)

# city-record key -> source column, for rebuilding CSV rows from the payload.
FROM_CITY = {
    "City": "city",
    "Country": "country",
    "Latitude": "lat",
    "Longitude": "lon",
    "Annual_Sunlight_Hours": "sunlight_hours",
    "GHI_kWh_per_m2": "ghi",
    "Solar_Installations_Count": "installations",
    "Avg_Annual_Production_kWh": "production_kwh",
    "Estimated_Annual_Savings_USD": "savings_usd",
    "Payback_Period_Years": "payback_years",
    "ROI_Percentage": "roi_pct",
    "CO2_Reduction_Tons_per_Year": "co2_tons",
    "Solar_Viability_Score": "viability",
    "Region": "region",
}

# Constant across all 48 rows; see the caveats in output/data.json.
CONSTANTS = {
    "Electricity_Price_USD_per_kWh": 0.15,
    "Avg_System_Cost_USD": 15000,
}

MEASURES: dict[str, tuple[str, str | None]] = {
    "Cities": ("COUNTROWS ( Cities )", "#,0"),
    "Countries": ("DISTINCTCOUNT ( Cities[Country] )", "#,0"),
    "Regions": ("DISTINCTCOUNT ( Cities[Region] )", "#,0"),
    "Total CO2 Tons": ("SUM ( Cities[CO2_Reduction_Tons_per_Year] )", "#,0.00"),
    "Total Installations": ("SUM ( Cities[Solar_Installations_Count] )", "#,0"),
    "Total Production kWh": ("SUM ( Cities[Avg_Annual_Production_kWh] )", "#,0"),
    "Mean ROI %": ("AVERAGE ( Cities[ROI_Percentage] )", "#,0.00"),
    "Mean Production kWh": ("AVERAGE ( Cities[Avg_Annual_Production_kWh] )", "#,0"),
    "Cities Low Risk": (
        'CALCULATE ( COUNTROWS ( Cities ), Cities[Payback Risk Band] = "Low" )', "#,0",
    ),
    "Cities Medium Risk": (
        'CALCULATE ( COUNTROWS ( Cities ), Cities[Payback Risk Band] = "Medium" )', "#,0",
    ),
    "Cities High Risk": (
        'CALCULATE ( COUNTROWS ( Cities ), Cities[Payback Risk Band] = "High" )', "#,0",
    ),
    # Dense rank on mean ROI, descending — matches regional_roi_rank().
    "Regional ROI Rank": (
        "IF (\n"
        "    NOT ISBLANK ( [Mean ROI %] ),\n"
        "    RANKX (\n"
        "        ALLSELECTED ( Cities[Region] ),\n"
        "        CALCULATE ( [Mean ROI %] ),\n"
        "        ,\n"
        "        DESC,\n"
        "        DENSE\n"
        "    )\n"
        ")",
        "#,0",
    ),
    # 1 - (sample sigma / mu), clamped to [0,1]; BLANK under 3 cities, because a
    # single-city region has no spread and would otherwise read as a perfect 1.
    "Production Consistency": (
        "VAR CityCount = COUNTROWS ( Cities )\n"
        "VAR Mu = AVERAGE ( Cities[Avg_Annual_Production_kWh] )\n"
        "VAR Sigma = STDEV.S ( Cities[Avg_Annual_Production_kWh] )\n"
        "RETURN\n"
        "    IF (\n"
        "        CityCount >= 3 && Mu <> 0,\n"
        "        MIN ( 1, MAX ( 0, 1 - DIVIDE ( Sigma, Mu ) ) ),\n"
        "        BLANK ()\n"
        "    )",
        "#,0.00",
    ),
    "Small Sample": ('IF ( COUNTROWS ( Cities ) < 5, "n = " & COUNTROWS ( Cities ), "" )', None),
}

PAGES = (
    {"id": "PageFinancial", "display": "Financial performance"},
    {"id": "PageProduction", "display": "Production"},
    {"id": "PageSustainability", "display": "Sustainability"},
)

_BASE = "https://developer.microsoft.com/json-schemas/fabric"
SCHEMA = {
    "platform": f"{_BASE}/gitIntegration/platformProperties/2.0.0/schema.json",
    "pbir": f"{_BASE}/item/report/definitionProperties/1.0.0/schema.json",
    "version": f"{_BASE}/item/report/definition/versionMetadata/1.0.0/schema.json",
    "report": f"{_BASE}/item/report/definition/report/1.0.0/schema.json",
    "pages": f"{_BASE}/item/report/definition/pagesMetadata/1.0.0/schema.json",
    "page": f"{_BASE}/item/report/definition/page/1.0.0/schema.json",
    "visual": f"{_BASE}/item/report/definition/visualContainer/1.0.0/schema.json",
}


class PowerBIBuildError(Exception):
    """Raised when the payload is unusable or the project cannot be written."""


# --- M literal --------------------------------------------------------------

def _m_value(value) -> str:
    if isinstance(value, str):
        return '"' + value.replace('"', '""') + '"'
    if isinstance(value, bool):
        return "true" if value else "false"
    return repr(value)


def city_rows(payload: dict) -> list[list]:
    """Rebuild full CSV-shaped rows from the city records."""
    rows = []
    for city in payload["cities"]:
        row = []
        for name, _m_type, _dt in COLUMNS:
            if name in CONSTANTS:
                row.append(CONSTANTS[name])
            elif name == "Daily_Peak_Sun_Hours":
                # Not carried on the city record; derived from annual hours.
                row.append(round(city["sunlight_hours"] / 365.0, 2))
            else:
                row.append(city[FROM_CITY[name]])
        rows.append(row)
    return rows


def m_expression(payload: dict) -> list[str]:
    """A typed literal table. No file path, so the model opens anywhere."""
    type_parts = ", ".join(f"#\"{name}\" = {m_type}" for name, m_type, _ in COLUMNS)
    lines = ["let", "    Source = #table(", f"        type table [{type_parts}],", "        {"]
    rows = city_rows(payload)
    for i, row in enumerate(rows):
        comma = "," if i < len(rows) - 1 else ""
        lines.append("            {" + ", ".join(_m_value(v) for v in row) + "}" + comma)
    lines += ["        }", "    )", "in", "    Source"]
    return lines


# --- semantic model ---------------------------------------------------------

def model_bim(payload: dict) -> dict:
    columns = [
        {
            "name": name,
            "dataType": data_type,
            "sourceColumn": name,
            "summarizeBy": "none",
            "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_URL, "col:" + name)),
        }
        for name, _m_type, data_type in COLUMNS
    ]
    columns.append({
        "name": "Payback Risk Band",
        "type": "calculated",
        "dataType": "string",
        "isDataTypeInferred": True,
        "summarizeBy": "none",
        "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_URL, "col:band")),
        "expression": [
            "IF (",
            "    Cities[Payback_Period_Years] < 7.0,",
            '    "Low",',
            "    IF ( Cities[Payback_Period_Years] <= 9.0, \"Medium\", \"High\" )",
            ")",
        ],
    })

    measures = []
    for name, (dax, fmt) in MEASURES.items():
        measure = {
            "name": name,
            "expression": dax.split("\n"),
            "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_URL, "measure:" + name)),
        }
        if fmt:
            measure["formatString"] = fmt
        measures.append(measure)

    return {
        "name": NAME,
        # 1550 is accepted by every Desktop build since 2019.
        "compatibilityLevel": 1550,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True,
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": [
                {
                    "name": "Cities",
                    "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_URL, "table:Cities")),
                    "columns": columns,
                    "measures": measures,
                    "partitions": [
                        {
                            "name": "Cities",
                            "mode": "import",
                            "source": {"type": "m", "expression": m_expression(payload)},
                        }
                    ],
                }
            ],
            "annotations": [
                {"name": "PBI_QueryOrder", "value": '["Cities"]'},
                {"name": "GeneratedBy", "value": "analysis/build_powerbi.py"},
            ],
        },
    }


# --- report (PBIR) ----------------------------------------------------------

def _field(kind: str, prop: str) -> dict:
    """A QueryExpressionContainer. PBIR names the table on the SourceRef."""
    return {kind: {"Expression": {"SourceRef": {"Entity": "Cities"}}, "Property": prop}}


def _projection(kind: str, prop: str) -> dict:
    return {
        "field": _field(kind, prop),
        "queryRef": f"Cities.{prop}",
        "nativeQueryRef": prop,
    }


def _column(prop: str) -> dict:
    return _projection("Column", prop)


def _measure(prop: str) -> dict:
    return _projection("Measure", prop)


def _name_for(page_id: str, index: int, title: str) -> str:
    """Unique per report, <= 50 chars, word characters only."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{page_id}:{index}:{title}").hex[:20]


def _visual(
    visual_type: str,
    x: int,
    y: int,
    width: int,
    height: int,
    title: str,
    roles: dict[str, list[dict]],
) -> dict:
    """One visual.json document, minus its name (assigned per page)."""
    document = {
        "$schema": SCHEMA["visual"],
        "name": title,  # replaced with a stable id by _page_visuals
        "position": {"x": x, "y": y, "z": 0, "width": width, "height": height, "tabOrder": 0},
        "visual": {
            "visualType": visual_type,
            "objects": {
                "title": [{
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "true"}}},
                        "text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
                    }
                }]
            },
            "drillFilterOtherVisuals": True,
        },
    }
    if roles:
        document["visual"]["query"] = {
            "queryState": {
                role: {"projections": projections} for role, projections in roles.items()
            }
        }
    return document


def _card(x: int, y: int, w: int, h: int, measure: str, title: str) -> dict:
    return _visual("card", x, y, w, h, title, {"Values": [_measure(measure)]})


def _slicer(x: int, y: int, w: int, h: int, column: str, title: str) -> dict:
    return _visual("slicer", x, y, w, h, title, {"Values": [_column(column)]})


def _bar(x: int, y: int, w: int, h: int, title: str, category: str, measure: str) -> dict:
    return _visual("barChart", x, y, w, h, title, {
        "Category": [_column(category)],
        "Y": [_measure(measure)],
    })


def _scatter(
    x: int, y: int, w: int, h: int, title: str, detail: str, x_measure: str, y_measure: str
) -> dict:
    return _visual("scatterChart", x, y, w, h, title, {
        "Category": [_column(detail)],
        "X": [_measure(x_measure)],
        "Y": [_measure(y_measure)],
    })


def _page_financial() -> list[dict]:
    return [
        _card(16, 16, 200, 100, "Cities", "Cities"),
        _card(228, 16, 200, 100, "Total CO2 Tons", "CO2 avoided (t/yr)"),
        _card(440, 16, 200, 100, "Total Installations", "Installations"),
        _card(652, 16, 200, 100, "Mean ROI %", "Mean ROI %"),
        _slicer(864, 16, 190, 250, "Region", "Region"),
        _slicer(1066, 16, 190, 250, "Payback Risk Band", "Payback risk"),
        _bar(16, 128, 500, 560, "ROI by city", "City", "Mean ROI %"),
        _bar(528, 128, 320, 270, "Cities at high payback risk", "Region", "Cities High Risk"),
        _bar(528, 410, 320, 278, "Mean ROI by region", "Region", "Mean ROI %"),
        _scatter(864, 278, 392, 410, "Installations vs ROI  (r = 0.137)",
                 "City", "Total Installations", "Mean ROI %"),
    ]


def _page_production() -> list[dict]:
    return [
        _card(16, 16, 220, 100, "Total Production kWh", "Production (kWh/yr)"),
        _card(248, 16, 220, 100, "Mean Production kWh", "Mean per city"),
        _slicer(864, 16, 190, 250, "Region", "Region"),
        _slicer(1066, 16, 190, 250, "Payback Risk Band", "Payback risk"),
        _bar(16, 128, 420, 560, "Mean production by country", "Country", "Mean Production kWh"),
        _bar(448, 128, 400, 270, "Installations by region", "Region", "Total Installations"),
        _bar(448, 410, 400, 278, "Production consistency by region", "Region",
             "Production Consistency"),
        _scatter(864, 278, 392, 410, "Irradiance vs production", "City",
                 "Mean ROI %", "Mean Production kWh"),
    ]


def _page_sustainability() -> list[dict]:
    return [
        _card(16, 16, 220, 100, "Total CO2 Tons", "CO2 avoided (t/yr)"),
        _card(248, 16, 220, 100, "Regions", "Regions"),
        _slicer(864, 16, 190, 100, "Region", "Region"),
        _slicer(1066, 16, 190, 100, "Payback Risk Band", "Payback risk"),
        _visual("pivotTable", 16, 128, 500, 560, "Region > country > city", {
            "Rows": [_column("Region"), _column("Country"), _column("City")],
            "Values": [_measure("Total CO2 Tons"), _measure("Total Installations")],
        }),
        _visual("map", 528, 128, 728, 300, "Cities by installed base", {
            "Category": [_column("City")],
            "Size": [_measure("Total Installations")],
        }),
        _bar(528, 440, 356, 248, "CO2 avoided by country", "Country", "Total CO2 Tons"),
        _scatter(896, 440, 360, 248, "ROI vs viability", "City",
                 "Mean ROI %", "Mean ROI %"),
    ]


PAGE_BUILDERS = {
    "PageFinancial": _page_financial,
    "PageProduction": _page_production,
    "PageSustainability": _page_sustainability,
}


def report_files(payload: dict) -> dict[str, dict]:
    """Every PBIR document, keyed by path relative to the Report folder."""
    files: dict[str, dict] = {
        "definition/version.json": {"$schema": SCHEMA["version"], "version": "1.0.0"},
        "definition/report.json": {
            "$schema": SCHEMA["report"],
            "layoutOptimization": "None",
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU06",
                    "reportVersionAtImport": "5.55",
                    "type": "SharedResources",
                }
            },
        },
        "definition/pages/pages.json": {
            "$schema": SCHEMA["pages"],
            "pageOrder": [page["id"] for page in PAGES],
            "activePageName": PAGES[0]["id"],
        },
    }

    for page in PAGES:
        page_id = page["id"]
        files[f"definition/pages/{page_id}/page.json"] = {
            "$schema": SCHEMA["page"],
            "name": page_id,
            "displayName": page["display"],
            "displayOption": "FitToPage",
            "width": CANVAS_WIDTH,
            "height": CANVAS_HEIGHT,
        }
        for index, visual in enumerate(PAGE_BUILDERS[page_id]()):
            visual["name"] = _name_for(page_id, index, visual["name"])
            files[
                f"definition/pages/{page_id}/visuals/{visual['name']}/visual.json"
            ] = visual

    return files
# --- writing ----------------------------------------------------------------

def _platform(item_type: str) -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": item_type, "displayName": NAME},
        "config": {
            "version": "2.0",
            "logicalId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"logical:{item_type}:{NAME}")),
        },
    }


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")


def build(data_path: Path, out_dir: Path) -> Path:
    """Read data.json, emit the PBIP project. Raises PowerBIBuildError."""
    data_path = Path(data_path)
    if not data_path.is_file():
        raise PowerBIBuildError(
            f"data payload not found: {data_path} — run `python -m analysis.build_data` first"
        )
    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PowerBIBuildError(f"could not parse {data_path}: {exc}") from exc

    missing = [key for key in REQUIRED_KEYS if key not in payload]
    if missing:
        raise PowerBIBuildError(f"payload missing required key(s): {missing}")
    if not payload["cities"]:
        raise PowerBIBuildError("payload contains no cities")

    out_dir = Path(out_dir)
    model_dir = out_dir / f"{NAME}.SemanticModel"
    report_dir = out_dir / f"{NAME}.Report"

    _write(out_dir / f"{NAME}.pbip", {
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })

    _write(model_dir / "definition.pbism", {"version": "1.0", "settings": {}})
    _write(model_dir / "model.bim", model_bim(payload))
    _write(model_dir / ".platform", _platform("SemanticModel"))

    _write(report_dir / "definition.pbir", {
        "$schema": SCHEMA["pbir"],
        # 4.0 or higher is what allows the definition/ folder (PBIR); below
        # that Desktop expects PBIR-Legacy report.json instead.
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
    })
    _write(report_dir / ".platform", _platform("Report"))

    # Rebuild the definition tree from scratch: a renamed or removed visual
    # would otherwise leave an orphan folder that Desktop still loads.
    definition = report_dir / "definition"
    if definition.exists():
        shutil.rmtree(definition)
    legacy = report_dir / "report.json"
    if legacy.exists():
        legacy.unlink()

    for relative, document in report_files(payload).items():
        _write(report_dir / relative, document)

    return out_dir / f"{NAME}.pbip"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a Power BI project (PBIP)")
    parser.add_argument("data", nargs="?", default="output/data.json")
    parser.add_argument("out", nargs="?", default="output/powerbi")
    args = parser.parse_args(argv)

    try:
        entry = build(Path(args.data), Path(args.out))
    except PowerBIBuildError as exc:
        print(f"POWER BI BUILD FAILED: {exc}", file=sys.stderr)
        return 1

    payload = json.loads(Path(args.data).read_text(encoding="utf-8"))
    t = payload["totals"]
    print(f"wrote {entry}")
    print("  open that file in Power BI Desktop. Expected on the financial page:")
    print(f"    Cities {t['cities']} | CO2 {t['co2_tons']:.2f} t | "
          f"Installations {t['installations']:,}")
    print("    Payback risk Low 5 / Medium 19 / High 24")
    print("    Regional ROI Rank 1 = Middle East; Asia CO2 = 54.72 (includes Dubai)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
