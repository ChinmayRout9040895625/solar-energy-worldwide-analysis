import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.build_powerbi import (
    MEASURES,
    PAGES,
    SCHEMA,
    PowerBIBuildError,
    build,
    main,
    model_bim,
    report_files,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "output" / "data.json"
NAME = "SolarEnergyWorldwide"


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


def _read(project: Path, relative: str) -> dict:
    return json.loads((project / relative).read_text(encoding="utf-8"))


# --- project skeleton -------------------------------------------------------

def test_every_required_file_is_written(project):
    expected = [
        f"{NAME}.pbip",
        f"{NAME}.SemanticModel/definition.pbism",
        f"{NAME}.SemanticModel/model.bim",
        f"{NAME}.SemanticModel/.platform",
        f"{NAME}.Report/definition.pbir",
        f"{NAME}.Report/.platform",
        f"{NAME}.Report/definition/version.json",
        f"{NAME}.Report/definition/report.json",
        f"{NAME}.Report/definition/pages/pages.json",
    ]
    missing = [name for name in expected if not (project / name).is_file()]
    assert missing == []


def test_the_legacy_report_json_is_not_emitted(project):
    """PBIR-Legacy report.json is documented as not externally editable; it is
    what a hand-written layout gets silently dropped from."""
    assert not (project / f"{NAME}.Report" / "report.json").is_file()


def test_every_emitted_file_is_valid_json(project):
    for path in project.rglob("*"):
        if path.is_file():
            json.loads(path.read_text(encoding="utf-8"))


def test_every_pbir_file_declares_its_schema(project):
    definition = project / f"{NAME}.Report" / "definition"
    for path in definition.rglob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        assert "$schema" in document, path
        assert document["$schema"].startswith("https://developer.microsoft.com/json-schemas/")


def test_report_declares_version_four_so_pbir_is_used(project):
    pbir = _read(project, f"{NAME}.Report/definition.pbir")
    # Versions below 4.0 pin the report to PBIR-Legacy report.json.
    assert pbir["version"] == "4.0"
    assert pbir["datasetReference"]["byPath"]["path"] == f"../{NAME}.SemanticModel"


def test_version_metadata_matches_the_documented_pattern(project):
    version = _read(project, f"{NAME}.Report/definition/version.json")["version"]
    assert re.fullmatch(r"[1-9][0-9]*\.(0|[1-9][0-9]*)\.0", version), version


def test_report_root_carries_the_required_schema_properties(project):
    report = _read(project, f"{NAME}.Report/definition/report.json")
    # layoutOptimization is a string enum in PBIR, not an integer.
    assert report["layoutOptimization"] in ("None", "PhonePortrait")
    base = report["themeCollection"]["baseTheme"]
    for key in ("name", "reportVersionAtImport", "type"):
        assert key in base
    assert base["type"] in ("RegisteredResources", "SharedResources")


# --- pages ------------------------------------------------------------------

def test_one_folder_per_page_each_with_a_page_json(project):
    pages_dir = project / f"{NAME}.Report" / "definition" / "pages"
    folders = sorted(p.name for p in pages_dir.iterdir() if p.is_dir())
    assert folders == sorted(page["id"] for page in PAGES)
    for folder in folders:
        assert (pages_dir / folder / "page.json").is_file()


def test_pages_metadata_orders_every_page(project):
    pages = _read(project, f"{NAME}.Report/definition/pages/pages.json")
    assert pages["pageOrder"] == [page["id"] for page in PAGES]
    assert pages["activePageName"] == PAGES[0]["id"]


def test_page_display_option_is_the_string_enum(project):
    for page in PAGES:
        document = _read(project, f"{NAME}.Report/definition/pages/{page['id']}/page.json")
        assert document["displayOption"] in (
            "DeprecatedDynamic", "FitToPage", "FitToWidth", "ActualSize", "ActualSizeTopLeft",
        )
        assert isinstance(document["width"], int)
        assert isinstance(document["height"], int)
        assert document["displayName"] == page["display"]
        assert len(document["name"]) <= 50


# --- visuals ----------------------------------------------------------------

def _visual_documents(project: Path) -> list[dict]:
    root = project / f"{NAME}.Report" / "definition" / "pages"
    return [json.loads(p.read_text(encoding="utf-8")) for p in root.rglob("visual.json")]


def test_every_page_has_visuals(project):
    root = project / f"{NAME}.Report" / "definition" / "pages"
    for page in PAGES:
        visuals = list((root / page["id"]).rglob("visual.json"))
        assert visuals, page["id"]


def test_each_visual_lives_in_its_own_folder_named_after_it(project):
    root = project / f"{NAME}.Report" / "definition" / "pages"
    for path in root.rglob("visual.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        assert path.parent.name == document["name"]
        assert path.parent.parent.name == "visuals"


def test_visual_names_are_unique_and_within_the_length_limit(project):
    names = [d["name"] for d in _visual_documents(project)]
    assert len(names) == len(set(names))
    for name in names:
        assert len(name) <= 50
        assert re.fullmatch(r"[\w-]+", name), name


def test_every_visual_declares_position_and_type(project):
    for document in _visual_documents(project):
        position = document["position"]
        for key in ("x", "y", "width", "height"):
            assert key in position, document["name"]
        assert position["x"] >= 0 and position["y"] >= 0
        assert document["visual"]["visualType"]


def test_visuals_stay_inside_the_canvas(project):
    pages = {p["id"]: p for p in PAGES}
    root = project / f"{NAME}.Report" / "definition" / "pages"
    for page_id in pages:
        page = _read(project, f"{NAME}.Report/definition/pages/{page_id}/page.json")
        for path in (root / page_id).rglob("visual.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            position = document["position"]
            assert position["x"] + position["width"] <= page["width"] + 1
            assert position["y"] + position["height"] <= page["height"] + 1


def test_every_projection_names_a_field_and_a_queryref(project):
    for document in _visual_documents(project):
        query = document["visual"].get("query")
        if not query:
            continue
        for role, state in query["queryState"].items():
            assert state["projections"], f"{document['name']} role {role} is empty"
            for projection in state["projections"]:
                assert "field" in projection
                assert "queryRef" in projection
                container = projection["field"]
                kind = next(iter(container))
                assert kind in ("Column", "Measure", "Aggregation")
                assert container[kind]["Expression"]["SourceRef"]["Entity"] == "Cities"
                assert container[kind]["Property"]


def test_every_field_a_visual_binds_to_exists_in_the_model(project, payload):
    """A visual bound to something the model does not define is the most likely
    way this project opens to an empty or broken page."""
    model = model_bim(payload)["model"]["tables"][0]
    defined = {m["name"] for m in model["measures"]} | {c["name"] for c in model["columns"]}

    used = set()
    for document in _visual_documents(project):
        query = document["visual"].get("query")
        if not query:
            continue
        for state in query["queryState"].values():
            for projection in state["projections"]:
                container = projection["field"]
                used.add(container[next(iter(container))]["Property"])

    assert used
    assert used <= defined, f"undefined in model: {sorted(used - defined)}"


def test_pages_carry_region_and_risk_slicers(project):
    types = [d["visual"]["visualType"] for d in _visual_documents(project)]
    assert types.count("slicer") >= 2


# --- semantic model ---------------------------------------------------------

def test_model_declares_one_table_with_the_source_columns(payload):
    tables = model_bim(payload)["model"]["tables"]
    assert len(tables) == 1
    names = {c["name"] for c in tables[0]["columns"]}
    for column in ("City", "Country", "Region", "ROI_Percentage", "Payback_Period_Years"):
        assert column in names


def test_model_carries_the_payback_risk_band_as_a_calculated_column(payload):
    cities = model_bim(payload)["model"]["tables"][0]
    band = next(c for c in cities["columns"] if c["name"] == "Payback Risk Band")
    assert band["type"] == "calculated"
    dax = "".join(band["expression"])
    assert "7.0" in dax and "9.0" in dax
    assert '"Low"' in dax and '"Medium"' in dax and '"High"' in dax


def test_data_is_embedded_so_the_model_needs_no_external_file(payload):
    m = "".join(model_bim(payload)["model"]["tables"][0]["partitions"][0]["source"]["expression"])
    assert "#table" in m
    assert "File.Contents" not in m, "an absolute file path would break on any other machine"
    assert "Csv.Document" not in m


def test_every_one_of_the_48_cities_is_embedded(payload):
    m = "".join(model_bim(payload)["model"]["tables"][0]["partitions"][0]["source"]["expression"])
    for city in payload["cities"]:
        assert f'"{city["city"]}"' in m, city["city"]


def test_dubai_is_embedded_with_its_real_figures(payload):
    m = "".join(model_bim(payload)["model"]["tables"][0]["partitions"][0]["source"]["expression"])
    dubai = next(c for c in payload["cities"] if c["city"] == "Dubai")
    assert '"Dubai"' in m and '"UAE"' in m
    assert str(dubai["installations"]) in m


def test_all_declared_measures_exist_in_the_model(payload):
    names = {m["name"] for m in model_bim(payload)["model"]["tables"][0]["measures"]}
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
    assert "3" in dax
    assert "BLANK" in dax.upper()


def test_measures_carry_format_strings(payload):
    measures = {m["name"]: m for m in model_bim(payload)["model"]["tables"][0]["measures"]}
    assert "formatString" in measures["Mean ROI %"]
    assert "formatString" in measures["Total CO2 Tons"]


def test_model_compatibility_level_suits_the_installed_desktop(payload):
    assert model_bim(payload)["compatibilityLevel"] <= 1550


# --- schema constants -------------------------------------------------------

def test_schema_urls_are_all_versioned_and_absolute():
    for key, url in SCHEMA.items():
        assert url.startswith("https://developer.microsoft.com/json-schemas/"), key
        assert url.endswith("/schema.json"), key


def test_report_files_keys_are_relative_paths(payload):
    for path in report_files(payload):
        assert not path.startswith("/")
        assert "\\" not in path, "use forward slashes so the layout is platform-stable"


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


def test_rebuild_replaces_a_stale_report_definition(tmp_path):
    """Regenerating must not leave orphaned visual folders from a prior run."""
    out = tmp_path / "out"
    build(DATA, out)
    stale = out / f"{NAME}.Report" / "definition" / "pages" / "GhostPage"
    stale.mkdir(parents=True)
    (stale / "page.json").write_text("{}", encoding="utf-8")
    build(DATA, out)
    assert not stale.exists(), "stale page survived a rebuild"


def test_main_returns_zero_on_success(tmp_path):
    assert main([str(DATA), str(tmp_path / "out")]) == 0


def test_main_returns_one_on_failure(tmp_path):
    assert main([str(tmp_path / "absent.json"), str(tmp_path / "out")]) == 1
