import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.build_pbit import (
    DEFAULT_SKELETON,
    PbitBuildError,
    build,
    layout_for,
    main,
    read_part,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "output" / "data.json"
SKELETON = Path(DEFAULT_SKELETON)

pytestmark = pytest.mark.skipif(
    not SKELETON.is_file(),
    reason=(
        "no skeleton template — export one once from Power BI Desktop: "
        "File > Export > Power BI template"
    ),
)


@pytest.fixture(scope="module")
def payload() -> dict:
    if not DATA.is_file():
        pytest.fail("output/data.json missing — run `python -m analysis.build_data`")
    return json.loads(DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def built(tmp_path_factory, payload) -> Path:
    out = tmp_path_factory.mktemp("pbit") / "SolarEnergyWorldwide.pbit"
    build(DATA, out, SKELETON)
    return out


# --- the container is copied, not rebuilt -----------------------------------

def test_security_bindings_are_dropped(built):
    """SecurityBindings binds to the package contents; rewriting any part
    invalidates it and Desktop calls the file corrupted."""
    with zipfile.ZipFile(built) as z:
        assert "SecurityBindings" not in z.namelist()
        manifest = z.read("[Content_Types].xml").decode("utf-8")
    assert "SecurityBindings" not in manifest


def test_every_other_part_of_the_skeleton_survives(built):
    with zipfile.ZipFile(SKELETON) as a, zipfile.ZipFile(built) as b:
        assert set(a.namelist()) - {"SecurityBindings"} == set(b.namelist())


def test_only_the_layout_part_differs_from_the_skeleton(built):
    """Everything else — SecurityBindings, DataModelSchema, Content_Types —
    is copied byte for byte. Rebuilding those is what got the file rejected."""
    changed = []
    with zipfile.ZipFile(SKELETON) as a, zipfile.ZipFile(built) as b:
        for name in a.namelist():
            if name == "SecurityBindings":
                continue
            if a.read(name) != b.read(name):
                changed.append(name)
    assert changed == ["Report/Layout", "[Content_Types].xml"] or changed == [
        "[Content_Types].xml", "Report/Layout",
    ], changed


def test_the_model_is_the_one_desktop_accepted(built, payload):
    schema = json.loads(read_part(built, "DataModelSchema"))
    table = schema["model"]["tables"][0]
    assert table["name"] == "Cities"
    names = {m["name"] for m in table["measures"]}
    for measure in ("Mean ROI %", "Total CO2 Tons", "Regional ROI Rank", "Production Consistency"):
        assert measure in names


# --- the layout we inject ---------------------------------------------------

def test_layout_keeps_the_skeleton_top_level_shape(built):
    skeleton = json.loads(read_part(SKELETON, "Report/Layout"))
    layout = json.loads(read_part(built, "Report/Layout"))
    assert set(layout.keys()) == set(skeleton.keys())
    assert layout["layoutOptimization"] == skeleton["layoutOptimization"]
    assert skeleton["sections"] == []
    # config is the skeleton's, plus an explicit opening page.
    before = json.loads(skeleton["config"])
    after = json.loads(layout["config"])
    assert after["activeSectionIndex"] == 0
    assert {k: v for k, v in after.items() if k != "activeSectionIndex"} == before


def test_three_pages_are_injected(built):
    layout = json.loads(read_part(built, "Report/Layout"))
    assert len(layout["sections"]) == 3
    assert [s["displayName"] for s in layout["sections"]] == [
        "Financial performance", "Production", "Sustainability",
    ]


def test_sections_use_integer_ids_and_display_option(built):
    for section in json.loads(read_part(built, "Report/Layout"))["sections"]:
        assert isinstance(section["id"], int)
        assert section["displayOption"] == 1
        assert section["width"] == 1280 and section["height"] == 720
        json.loads(section["config"])
        json.loads(section["filters"])


def test_every_visual_carries_config_query_and_datatransforms(built):
    """A container with only `config` renders as nothing — the defect behind
    the first blank report."""
    for section in json.loads(read_part(built, "Report/Layout"))["sections"]:
        assert section["visualContainers"]
        for visual in section["visualContainers"]:
            for key in ("config", "query", "dataTransforms", "filters"):
                assert key in visual, key
                json.loads(visual[key])


def test_query_uses_the_from_alias_and_transforms_use_the_entity(built):
    for section in json.loads(read_part(built, "Report/Layout"))["sections"]:
        for visual in section["visualContainers"]:
            command = json.loads(visual["query"])["Commands"][0]["SemanticQueryDataShapeCommand"]
            for item in command["Query"]["Select"]:
                kind = next(k for k in ("Column", "Measure") if k in item)
                assert item[kind]["Expression"]["SourceRef"] == {"Source": "c"}
            for select in json.loads(visual["dataTransforms"])["selects"]:
                expr = select["expr"]
                node = expr[next(iter(expr))]
                assert node["Expression"]["SourceRef"] == {"Entity": "Cities"}


def test_prototype_query_matches_the_executed_query(built):
    for section in json.loads(read_part(built, "Report/Layout"))["sections"]:
        for visual in section["visualContainers"]:
            proto = json.loads(visual["config"])["singleVisual"]["prototypeQuery"]
            command = json.loads(visual["query"])["Commands"][0]["SemanticQueryDataShapeCommand"]
            assert proto["Select"] == command["Query"]["Select"]


def test_every_bound_field_exists_in_the_model(built):
    schema = json.loads(read_part(built, "DataModelSchema"))
    table = schema["model"]["tables"][0]
    defined = {m["name"] for m in table["measures"]} | {c["name"] for c in table["columns"]}

    used = set()
    for section in json.loads(read_part(built, "Report/Layout"))["sections"]:
        for visual in section["visualContainers"]:
            for item in json.loads(visual["config"])["singleVisual"]["prototypeQuery"]["Select"]:
                kind = next(k for k in ("Column", "Measure") if k in item)
                used.add(item[kind]["Property"])

    assert used
    assert used <= defined, f"not in the model: {sorted(used - defined)}"


def test_visual_names_are_unique(built):
    names = [
        json.loads(v["config"])["name"]
        for s in json.loads(read_part(built, "Report/Layout"))["sections"]
        for v in s["visualContainers"]
    ]
    assert len(names) == len(set(names))


def test_visuals_fit_the_page(built):
    for section in json.loads(read_part(built, "Report/Layout"))["sections"]:
        for visual in section["visualContainers"]:
            assert visual["x"] >= 0 and visual["y"] >= 0
            assert visual["x"] + visual["width"] <= section["width"]
            assert visual["y"] + visual["height"] <= section["height"]


def test_slicers_present_for_cross_filtering(built):
    types = [
        json.loads(v["config"])["singleVisual"]["visualType"]
        for s in json.loads(read_part(built, "Report/Layout"))["sections"]
        for v in s["visualContainers"]
    ]
    assert types.count("slicer") >= 2


def test_layout_part_is_utf16le_without_a_bom(built):
    with zipfile.ZipFile(built) as z:
        raw = z.read("Report/Layout")
    assert not raw.startswith(b"\xff\xfe")
    raw.decode("utf-16-le")


def test_layout_for_is_pure(payload):
    a = layout_for(payload, {"report": {}, "sections": [], "config": "{}", "layoutOptimization": 0})
    b = layout_for(payload, {"report": {}, "sections": [], "config": "{}", "layoutOptimization": 0})
    assert a == b


# --- failure paths ----------------------------------------------------------

def test_build_raises_on_missing_skeleton(tmp_path):
    with pytest.raises(PbitBuildError) as excinfo:
        build(DATA, tmp_path / "x.pbit", tmp_path / "absent.pbit")
    assert "absent.pbit" in str(excinfo.value)


def test_build_raises_when_the_skeleton_is_not_a_template(tmp_path):
    fake = tmp_path / "fake.pbit"
    with zipfile.ZipFile(fake, "w") as z:
        z.writestr("Version", b"x")
    with pytest.raises(PbitBuildError) as excinfo:
        build(DATA, tmp_path / "x.pbit", fake)
    assert "Report/Layout" in str(excinfo.value)


def test_build_raises_on_missing_payload(tmp_path):
    with pytest.raises(PbitBuildError):
        build(tmp_path / "absent.json", tmp_path / "x.pbit", SKELETON)


def test_main_returns_zero_on_success(tmp_path):
    assert main([str(DATA), str(tmp_path / "x.pbit"), str(SKELETON)]) == 0


def test_main_returns_one_on_failure(tmp_path):
    assert main([str(DATA), str(tmp_path / "x.pbit"), str(tmp_path / "absent.pbit")]) == 1


def test_bar_charts_sort_descending_by_their_measure(built):
    """Without an OrderBy, Power BI sorts the category alphabetically; the
    spec wants ROI by city ranked."""
    sorted_bars = 0
    for section in json.loads(read_part(built, "Report/Layout"))["sections"]:
        for visual in section["visualContainers"]:
            config = json.loads(visual["config"])
            if config["singleVisual"]["visualType"] != "clusteredBarChart":
                continue
            sorted_bars += 1
            order = config["singleVisual"]["prototypeQuery"]["OrderBy"]
            assert order[0]["Direction"] == 2, config["name"]
            measure = order[0]["Expression"]["Measure"]["Property"]
            marked = [
                s for s in json.loads(visual["dataTransforms"])["selects"]
                if s.get("sort") == 2
            ]
            assert len(marked) == 1 and marked[0]["queryName"].endswith(measure)
    assert sorted_bars >= 6
