import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.build_powerbi import (
    MEASURES,
    PAGES,
    PowerBIBuildError,
    build,
    main,
    model_bim,
    report_json,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "output" / "data.json"


@pytest.fixture(scope="module")
def payload() -> dict:
    if not DATA.is_file():
        pytest.fail("output/data.json missing — run `python -m analysis.build_data`")
    return json.loads(DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def project(tmp_path_factory, payload) -> Path:
    out = tmp_path_factory.mktemp("pbip")
    build(DATA, out)
    return out


# --- project skeleton -------------------------------------------------------

def test_every_required_file_is_written(project):
    expected = [
        "SolarEnergyWorldwide.pbip",
        "SolarEnergyWorldwide.SemanticModel/definition.pbism",
        "SolarEnergyWorldwide.SemanticModel/model.bim",
        "SolarEnergyWorldwide.SemanticModel/.platform",
        "SolarEnergyWorldwide.Report/definition.pbir",
        "SolarEnergyWorldwide.Report/report.json",
        "SolarEnergyWorldwide.Report/.platform",
    ]
    missing = [name for name in expected if not (project / name).is_file()]
    assert missing == []


def test_every_emitted_file_is_valid_json(project):
    for path in project.rglob("*"):
        if path.is_file():
            json.loads(path.read_text(encoding="utf-8"))  # must not raise


def test_pbip_points_at_the_report_folder(project):
    pbip = json.loads((project / "SolarEnergyWorldwide.pbip").read_text(encoding="utf-8"))
    assert pbip["artifacts"][0]["report"]["path"] == "SolarEnergyWorldwide.Report"


def test_report_references_the_model_by_relative_path(project):
    pbir = json.loads(
        (project / "SolarEnergyWorldwide.Report" / "definition.pbir").read_text(encoding="utf-8")
    )
    path = pbir["datasetReference"]["byPath"]["path"]
    assert path == "../SolarEnergyWorldwide.SemanticModel"
    assert not path.startswith("/") and ":" not in path, "must be relative, not absolute"


def test_legacy_format_versions_are_declared(project):
    pbir = json.loads(
        (project / "SolarEnergyWorldwide.Report" / "definition.pbir").read_text(encoding="utf-8")
    )
    pbism = json.loads(
        (project / "SolarEnergyWorldwide.SemanticModel" / "definition.pbism").read_text(encoding="utf-8")
    )
    # Version 1.0 pins report.json / model.bim, which the installed Desktop
    # reads with no preview feature enabled.
    assert pbir["version"] == "1.0"
    assert pbism["version"] == "1.0"


# --- semantic model ---------------------------------------------------------

def test_model_declares_one_table_with_the_source_columns(payload):
    model = model_bim(payload)
    tables = model["model"]["tables"]
    assert len(tables) == 1
    cities = tables[0]
    assert cities["name"] == "Cities"
    names = {c["name"] for c in cities["columns"]}
    for column in ("City", "Country", "Region", "ROI_Percentage", "Payback_Period_Years"):
        assert column in names


def test_model_carries_the_payback_risk_band_as_a_calculated_column(payload):
    cities = model_bim(payload)["model"]["tables"][0]
    band = next(c for c in cities["columns"] if c["name"] == "Payback Risk Band")
    assert band["type"] == "calculated"
    # Low < 7.0 <= Medium <= 9.0 < High, same boundaries as analysis/metrics.py
    dax = "".join(band["expression"])
    assert "7.0" in dax and "9.0" in dax
    assert '"Low"' in dax and '"Medium"' in dax and '"High"' in dax


def test_data_is_embedded_so_the_model_needs_no_external_file(payload):
    cities = model_bim(payload)["model"]["tables"][0]
    m = "".join(cities["partitions"][0]["source"]["expression"])
    assert "#table" in m
    assert "File.Contents" not in m, "an absolute file path would break on any other machine"
    assert "Csv.Document" not in m
    for city in ("New York", "Dubai", "Tel Aviv"):
        assert city in m


def test_every_one_of_the_48_cities_is_embedded(payload):
    cities = model_bim(payload)["model"]["tables"][0]
    m = "".join(cities["partitions"][0]["source"]["expression"])
    for city in payload["cities"]:
        assert f'"{city["city"]}"' in m, city["city"]


def test_dubai_is_embedded_with_its_real_figures(payload):
    """The reference dashboard dropped Dubai; the model must not."""
    m = "".join(model_bim(payload)["model"]["tables"][0]["partitions"][0]["source"]["expression"])
    dubai = next(c for c in payload["cities"] if c["city"] == "Dubai")
    assert '"Dubai"' in m
    assert '"UAE"' in m
    assert str(dubai["installations"]) in m


def test_all_declared_measures_exist_in_the_model(payload):
    cities = model_bim(payload)["model"]["tables"][0]
    names = {m["name"] for m in cities["measures"]}
    assert set(MEASURES) <= names


def test_key_measures_are_present_by_name(payload):
    names = {m["name"] for m in model_bim(payload)["model"]["tables"][0]["measures"]}
    for measure in (
        "Cities", "Countries", "Total CO2 Tons", "Total Installations",
        "Mean ROI %", "Regional ROI Rank", "Production Consistency",
        "Cities Low Risk", "Cities Medium Risk", "Cities High Risk",
    ):
        assert measure in names


def test_production_consistency_guards_the_small_sample_rule(payload):
    measures = {m["name"]: m for m in model_bim(payload)["model"]["tables"][0]["measures"]}
    dax = "".join(measures["Production Consistency"]["expression"])
    # Fewer than 3 cities must return BLANK, never 1.0.
    assert "3" in dax
    assert "BLANK" in dax.upper()


def test_measures_carry_format_strings(payload):
    measures = {m["name"]: m for m in model_bim(payload)["model"]["tables"][0]["measures"]}
    assert "formatString" in measures["Mean ROI %"]
    assert "formatString" in measures["Total CO2 Tons"]


def test_model_compatibility_level_suits_the_installed_desktop(payload):
    # 1550 is accepted by every Desktop build since 2019; newer levels are not.
    assert model_bim(payload)["compatibilityLevel"] <= 1550


# --- report -----------------------------------------------------------------

def test_report_has_the_three_pages(payload):
    sections = report_json(payload)["sections"]
    assert len(sections) == len(PAGES) == 3
    assert [s["displayName"] for s in sections] == [p["display"] for p in PAGES]


def test_every_page_carries_visuals(payload):
    for section in report_json(payload)["sections"]:
        assert len(section["visualContainers"]) > 0, section["displayName"]


def test_nested_config_strings_are_valid_json(payload):
    report = report_json(payload)
    json.loads(report["config"])
    for section in report["sections"]:
        json.loads(section["config"])
        json.loads(section["filters"])
        for visual in section["visualContainers"]:
            json.loads(visual["config"])
            json.loads(visual["filters"])


def test_every_visual_declares_a_position_inside_the_canvas(payload):
    for section in report_json(payload)["sections"]:
        for visual in section["visualContainers"]:
            assert visual["x"] >= 0 and visual["y"] >= 0
            assert visual["x"] + visual["width"] <= section["width"] + 1
            assert visual["y"] + visual["height"] <= section["height"] + 1


def test_every_measure_a_visual_uses_actually_exists(payload):
    """A visual bound to a measure the model does not define is the single most
    likely way this project opens to a broken page."""
    defined = {m["name"] for m in model_bim(payload)["model"]["tables"][0]["measures"]}
    defined |= {c["name"] for c in model_bim(payload)["model"]["tables"][0]["columns"]}

    used = set()
    for section in report_json(payload)["sections"]:
        for visual in section["visualContainers"]:
            config = json.loads(visual["config"])
            query = config.get("singleVisual", {}).get("prototypeQuery")
            if not query:
                continue
            for item in query["Select"]:
                if "Measure" in item:
                    used.add(item["Measure"]["Property"])
                elif "Column" in item:
                    used.add(item["Column"]["Property"])

    assert used, "no visual bound to anything"
    assert used <= defined, f"undefined in model: {sorted(used - defined)}"


def test_every_visual_has_a_unique_name(payload):
    names = []
    for section in report_json(payload)["sections"]:
        for visual in section["visualContainers"]:
            names.append(json.loads(visual["config"])["name"])
    assert len(names) == len(set(names))


def test_pages_carry_region_and_risk_slicers(payload):
    """The spec's cross-filtering requirement; in Power BI that is a slicer."""
    types = []
    for section in report_json(payload)["sections"]:
        for visual in section["visualContainers"]:
            config = json.loads(visual["config"])
            types.append(config.get("singleVisual", {}).get("visualType"))
    assert types.count("slicer") >= 2


# --- failure paths ----------------------------------------------------------

def test_build_raises_on_missing_payload(tmp_path):
    with pytest.raises(PowerBIBuildError) as excinfo:
        build(tmp_path / "absent.json", tmp_path / "out")
    assert "absent.json" in str(excinfo.value)


def test_build_raises_on_malformed_payload(tmp_path):
    broken = tmp_path / "data.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(PowerBIBuildError):
        build(broken, tmp_path / "out")


def test_build_raises_when_a_required_key_is_missing(tmp_path, payload):
    trimmed = {k: v for k, v in payload.items() if k != "cities"}
    path = tmp_path / "data.json"
    path.write_text(json.dumps(trimmed), encoding="utf-8")
    with pytest.raises(PowerBIBuildError) as excinfo:
        build(path, tmp_path / "out")
    assert "cities" in str(excinfo.value)


def test_main_returns_zero_on_success(tmp_path):
    assert main([str(DATA), str(tmp_path / "out")]) == 0


def test_main_returns_one_on_failure(tmp_path):
    assert main([str(tmp_path / "absent.json"), str(tmp_path / "out")]) == 1
