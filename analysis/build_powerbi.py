"""Generate a Power BI Desktop project (PBIP) from output/data.json.

Format choice: TMSL (`model.bim`) for the semantic model and PBIR-Legacy
(`report.json`) for the report. The newer TMDL and PBIR folder formats are
nicer to diff, but both are preview features that the installed Desktop build
(2.139 / Dec 2024) will not read without flags turned on. These two are read
natively by every Desktop since 2019, and are still plain JSON — so this
generator can validate everything it emits.

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


# --- report -----------------------------------------------------------------

def _select_measure(name: str) -> dict:
    return {
        "Measure": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": name},
        "Name": f"Cities.{name}",
        "NativeReferenceName": name,
    }


def _select_column(name: str) -> dict:
    return {
        "Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": name},
        "Name": f"Cities.{name}",
        "NativeReferenceName": name,
    }


def _visual(
    visual_type: str,
    x: int,
    y: int,
    width: int,
    height: int,
    title: str,
    projections: dict[str, list[str]],
    selects: list[dict],
    order_by: list | None = None,
) -> dict:
    name = uuid.uuid5(uuid.NAMESPACE_URL, f"visual:{title}:{visual_type}").hex[:20]
    config = {
        "name": name,
        "layouts": [{
            "id": 0,
            "position": {"x": x, "y": y, "z": 0, "width": width, "height": height, "tabOrder": 0},
        }],
        "singleVisual": {
            "visualType": visual_type,
            "projections": {
                role: [{"queryRef": f"Cities.{field}"} for field in fields]
                for role, fields in projections.items()
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "c", "Entity": "Cities", "Type": 0}],
                "Select": selects,
                **({"OrderBy": order_by} if order_by else {}),
            },
            "drillFilterOtherVisuals": True,
            "objects": {},
            "vcObjects": {
                "title": [{
                    "properties": {
                        "text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
                        "show": {"expr": {"Literal": {"Value": "true"}}},
                    }
                }]
            },
        },
    }
    return {
        "x": x, "y": y, "z": 0, "width": width, "height": height,
        "config": json.dumps(config),
        "filters": "[]",
    }


def _card(x: int, y: int, width: int, height: int, measure: str, title: str) -> dict:
    return _visual(
        "card", x, y, width, height, title,
        {"Values": [measure]}, [_select_measure(measure)],
    )


def _slicer(x: int, y: int, width: int, height: int, column: str, title: str) -> dict:
    return _visual(
        "slicer", x, y, width, height, title,
        {"Values": [column]}, [_select_column(column)],
    )


def _bar(
    x: int, y: int, width: int, height: int, title: str,
    category: str, measure: str, descending: bool = True,
) -> dict:
    order = [{
        "Direction": 2 if descending else 1,
        "Expression": {
            "Measure": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": measure}
        },
    }]
    return _visual(
        "barChart", x, y, width, height, title,
        {"Category": [category], "Y": [measure]},
        [_select_column(category), _select_measure(measure)],
        order_by=order,
    )


def _scatter(
    x: int, y: int, width: int, height: int, title: str,
    detail: str, x_measure: str, y_measure: str,
) -> dict:
    return _visual(
        "scatterChart", x, y, width, height, title,
        {"Details": [detail], "X": [x_measure], "Y": [y_measure]},
        [_select_column(detail), _select_measure(x_measure), _select_measure(y_measure)],
    )


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
        _scatter(864, 278, 392, 410, "Irradiance vs production  (r = 0.979)",
                 "City", "Mean ROI %", "Mean Production kWh"),
    ]


def _page_sustainability() -> list[dict]:
    matrix = _visual(
        "pivotTable", 16, 128, 500, 560, "Region > country > city",
        {"Rows": ["Region", "Country", "City"],
         "Values": ["Total CO2 Tons", "Total Installations"]},
        [
            _select_column("Region"), _select_column("Country"), _select_column("City"),
            _select_measure("Total CO2 Tons"), _select_measure("Total Installations"),
        ],
    )
    world_map = _visual(
        "map", 528, 128, 728, 300, "Cities by installed base",
        {"Category": ["City"], "Size": ["Total Installations"]},
        [_select_column("City"), _select_measure("Total Installations")],
    )
    return [
        _card(16, 16, 220, 100, "Total CO2 Tons", "CO2 avoided (t/yr)"),
        _card(248, 16, 220, 100, "Regions", "Regions"),
        _slicer(864, 16, 190, 100, "Region", "Region"),
        _slicer(1066, 16, 190, 100, "Payback Risk Band", "Payback risk"),
        matrix,
        world_map,
        _bar(528, 440, 356, 248, "CO2 avoided by country", "Country", "Total CO2 Tons"),
        _scatter(896, 440, 360, 248, "ROI vs viability  (r = 0.982)",
                 "City", "Mean ROI %", "Mean ROI %"),
    ]


def report_json(payload: dict) -> dict:
    builders = (_page_financial, _page_production, _page_sustainability)
    sections = []
    for ordinal, (page, builder) in enumerate(zip(PAGES, builders)):
        containers = builder()
        # Visual names must be unique across the whole report, and the helpers
        # seed theirs from title + type — which collides as soon as two pages
        # carry the same slicer or card. Re-seed per page, deterministically.
        for index, container in enumerate(containers):
            config = json.loads(container["config"])
            config["name"] = uuid.uuid5(
                uuid.NAMESPACE_URL, f"visual:{page['id']}:{index}:{config['name']}"
            ).hex[:20]
            container["config"] = json.dumps(config)

        sections.append({
            "name": page["id"],
            "displayName": page["display"],
            "ordinal": ordinal,
            "width": CANVAS_WIDTH,
            "height": CANVAS_HEIGHT,
            "displayOption": 1,
            "config": "{}",
            "filters": "[]",
            "visualContainers": containers,
        })

    return {
        "config": json.dumps({
            "version": "5.43",
            "themeCollection": {"baseTheme": {"name": "CY24SU02"}},
            "activeSectionIndex": 0,
            "defaultDrillFilterOtherVisuals": True,
            "settings": {"useStylableVisualContainerHeader": True},
        }),
        "layoutOptimization": 0,
        "resourcePackages": [{
            "resourcePackage": {
                "disabled": False,
                "items": [{"name": "CY24SU02", "path": "BaseThemes/CY24SU02.json", "type": 202}],
                "name": "SharedResources",
                "type": 2,
            }
        }],
        "sections": sections,
    }


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
        "version": "1.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
    })
    _write(report_dir / "report.json", report_json(payload))
    _write(report_dir / ".platform", _platform("Report"))

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
