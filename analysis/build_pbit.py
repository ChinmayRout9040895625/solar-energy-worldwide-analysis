"""Inject the report layout into a Power BI template exported by Desktop.

This does NOT build a .pbit from scratch. Three attempts at authoring Power BI
report containers from inference failed — the last one was rejected outright
("This file is corrupted or was created by an unrecognized version") because a
.pbit also needs a `SecurityBindings` part, which is a DPAPI blob that cannot be
synthesised, and a `DiagramLayout`, and a Content_Types manifest listing exactly
those parts.

So the skeleton comes from Power BI Desktop itself:

    File > Export > Power BI template

That file already contains a valid container and the semantic model Desktop
accepted. This module copies every part of it byte for byte and replaces only
`Report/Layout`. One part changes; everything Desktop is fussy about is
untouched.

Re-export the skeleton whenever the model changes — its DataModelSchema, not
data.json, is what the emitted template carries.

Layout shape was read off a real .pbix rather than recalled. The part that
matters: each visualContainer needs three sibling documents, not one —
`config`, plus `query` (a SemanticQueryDataShapeCommand with a Binding) and
`dataTransforms` (selects + projectionOrdering). A container with only a
`config` renders as nothing, which is what made the first attempt look blank.

Two shapes that look interchangeable and are not:
  * the query's Select uses SourceRef.Source — the From alias, "c"
  * dataTransforms' expr uses SourceRef.Entity — the table name, "Cities"

Run after `python -m analysis.build_data`:

    python -m analysis.build_pbit
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
import zipfile
from pathlib import Path

from analysis.build_powerbi import CANVAS_HEIGHT, CANVAS_WIDTH, PAGES, REQUIRED_KEYS

# Exported once from Desktop; see the module docstring.
DEFAULT_SKELETON = "SolarEnergyWorldwide.pbit"
LAYOUT_PART = "Report/Layout"
SECURITY_PART = "SecurityBindings"
CONTENT_TYPES_PART = "[Content_Types].xml"


def _drop_security_override(raw: bytes) -> bytes:
    """Remove the SecurityBindings entry from the Content_Types manifest."""
    text = raw.decode("utf-8")
    marker = '<Override PartName="/SecurityBindings" ContentType="" />'
    return text.replace(marker, "").encode("utf-8")

ALIAS = "c"
ENTITY = "Cities"
TYPE_TEXT = 1
TYPE_NUMBER = 259


class PbitBuildError(Exception):
    """Raised when the skeleton or payload is unusable."""


def read_part(pbit: Path, name: str) -> str:
    """Read a UTF-16LE part out of a template."""
    with zipfile.ZipFile(pbit) as z:
        return z.read(name).decode("utf-16-le")


# --- visuals ----------------------------------------------------------------

def _select(kind: str, prop: str) -> dict:
    return {
        kind: {"Expression": {"SourceRef": {"Source": ALIAS}}, "Property": prop},
        "Name": f"{ENTITY}.{prop}",
        "NativeReferenceName": prop,
    }


def _visual(
    visual_type: str,
    x: int,
    y: int,
    width: int,
    height: int,
    title: str,
    roles: list[tuple[str, str, str]],
) -> dict:
    """One visualContainer. `roles` is [(role, kind, property), ...] in order."""
    selects = [_select(kind, prop) for _r, kind, prop in roles]
    query = {
        "Version": 2,
        "From": [{"Name": ALIAS, "Entity": ENTITY, "Type": 0}],
        "Select": selects,
    }

    projections: dict[str, list[dict]] = {}
    for index, (role, _kind, prop) in enumerate(roles):
        entry = {"queryRef": f"{ENTITY}.{prop}"}
        if index == 0:
            entry["active"] = True
        projections.setdefault(role, []).append(entry)

    config = {
        "name": title,  # replaced per page in layout_for
        "layouts": [{
            "id": 0,
            "position": {"x": x, "y": y, "z": 0, "width": width, "height": height, "tabOrder": 0},
        }],
        "singleVisual": {
            "visualType": visual_type,
            "projections": projections,
            "prototypeQuery": query,
            "drillFilterOtherVisuals": True,
            "objects": {},
            "vcObjects": {
                "title": [{
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "true"}}},
                        "text": {"expr": {"Literal": {"Value": "'" + title.replace("'", "") + "'"}}},
                    }
                }]
            },
        },
    }

    command = {
        "SemanticQueryDataShapeCommand": {
            "Query": query,
            "Binding": {
                "Primary": {"Groupings": [{"Projections": list(range(len(selects)))}]},
                "DataReduction": {"DataVolume": 4, "Primary": {"Top": {}}},
                "Version": 1,
            },
            "ExecutionMetricsKind": 1,
        }
    }

    ordering: dict[str, list[int]] = {}
    transform_selects = []
    for index, (role, kind, prop) in enumerate(roles):
        ordering.setdefault(role, []).append(index)
        transform_selects.append({
            "displayName": prop,
            "queryName": f"{ENTITY}.{prop}",
            "roles": {role: True},
            "type": {
                "category": None,
                "underlyingType": TYPE_TEXT if kind == "Column" else TYPE_NUMBER,
            },
            "expr": {kind: {"Expression": {"SourceRef": {"Entity": ENTITY}}, "Property": prop}},
        })

    transforms = {
        "objects": {},
        "projectionOrdering": ordering,
        "selects": transform_selects,
    }

    return {
        "x": x, "y": y, "z": 0, "width": width, "height": height,
        "config": json.dumps(config),
        "filters": "[]",
        "query": json.dumps({"Commands": [command]}),
        "dataTransforms": json.dumps(transforms),
    }


def _card(x, y, w, h, measure, title):
    return _visual("card", x, y, w, h, title, [("Values", "Measure", measure)])


def _slicer(x, y, w, h, column, title):
    return _visual("slicer", x, y, w, h, title, [("Values", "Column", column)])


def _bar(x, y, w, h, title, category, measure):
    return _visual("clusteredBarChart", x, y, w, h, title, [
        ("Category", "Column", category),
        ("Y", "Measure", measure),
    ])


def _scatter(x, y, w, h, title, detail, xm, ym):
    return _visual("scatterChart", x, y, w, h, title, [
        ("Category", "Column", detail),
        ("X", "Measure", xm),
        ("Y", "Measure", ym),
    ])


def _page_financial() -> list[dict]:
    return [
        _card(16, 16, 200, 100, "Cities", "Cities"),
        _card(228, 16, 200, 100, "Total CO2 Tons", "CO2 avoided t/yr"),
        _card(440, 16, 200, 100, "Total Installations", "Installations"),
        _card(652, 16, 200, 100, "Mean ROI %", "Mean ROI %"),
        _slicer(864, 16, 190, 240, "Region", "Region"),
        _slicer(1066, 16, 190, 240, "Payback Risk Band", "Payback risk"),
        _bar(16, 128, 500, 560, "ROI by city", "City", "Mean ROI %"),
        _bar(528, 128, 320, 270, "Cities at high payback risk", "Region", "Cities High Risk"),
        _bar(528, 410, 320, 278, "Mean ROI by region", "Region", "Mean ROI %"),
        _scatter(864, 268, 392, 420, "Installations vs ROI",
                 "City", "Total Installations", "Mean ROI %"),
    ]


def _page_production() -> list[dict]:
    return [
        _card(16, 16, 220, 100, "Total Production kWh", "Production kWh/yr"),
        _card(248, 16, 220, 100, "Mean Production kWh", "Mean per city"),
        _slicer(864, 16, 190, 240, "Region", "Region"),
        _slicer(1066, 16, 190, 240, "Payback Risk Band", "Payback risk"),
        _bar(16, 128, 420, 560, "Mean production by country", "Country", "Mean Production kWh"),
        _bar(448, 128, 400, 270, "Installations by region", "Region", "Total Installations"),
        _bar(448, 410, 400, 278, "Production consistency", "Region", "Production Consistency"),
        _scatter(864, 268, 392, 420, "Production vs ROI",
                 "City", "Mean Production kWh", "Mean ROI %"),
    ]


def _page_sustainability() -> list[dict]:
    return [
        _card(16, 16, 220, 100, "Total CO2 Tons", "CO2 avoided t/yr"),
        _card(248, 16, 220, 100, "Regions", "Regions"),
        _slicer(864, 16, 190, 100, "Region", "Region"),
        _slicer(1066, 16, 190, 100, "Payback Risk Band", "Payback risk"),
        _visual("tableEx", 16, 128, 500, 560, "Region, country and city", [
            ("Values", "Column", "Region"),
            ("Values", "Column", "Country"),
            ("Values", "Column", "City"),
            ("Values", "Measure", "Total CO2 Tons"),
            ("Values", "Measure", "Total Installations"),
        ]),
        _bar(528, 128, 728, 270, "CO2 avoided by country", "Country", "Total CO2 Tons"),
        _bar(528, 410, 356, 278, "Installations by country", "Country", "Total Installations"),
        _scatter(896, 410, 360, 278, "CO2 vs installations",
                 "City", "Total Installations", "Total CO2 Tons"),
    ]


PAGE_BUILDERS = (_page_financial, _page_production, _page_sustainability)


def layout_for(payload: dict, skeleton_layout: dict) -> dict:
    """The skeleton's own layout with our sections filled in.

    Everything the skeleton set — config, layoutOptimization, the `report`
    block — is carried through untouched; only `sections` is populated.
    """
    sections = []
    for ordinal, (page, builder) in enumerate(zip(PAGES, PAGE_BUILDERS)):
        containers = builder()
        # Visual names must be unique report-wide; the same slicer appears on
        # more than one page, so re-seed per page.
        for index, container in enumerate(containers):
            config = json.loads(container["config"])
            config["name"] = uuid.uuid5(
                uuid.NAMESPACE_URL, f"{page['id']}:{index}:{config['name']}"
            ).hex[:20]
            container["config"] = json.dumps(config)

        sections.append({
            "id": ordinal,
            "name": uuid.uuid5(uuid.NAMESPACE_URL, "section:" + page["id"]).hex[:20],
            "displayName": page["display"],
            "filters": "[]",
            "ordinal": ordinal,
            "config": "{}",
            "displayOption": 1,
            "width": CANVAS_WIDTH,
            "height": CANVAS_HEIGHT,
            "visualContainers": containers,
        })

    layout = dict(skeleton_layout)
    layout["sections"] = sections
    return layout


def build(data_path: Path, out_path: Path, skeleton_path: Path) -> Path:
    """Copy the skeleton, swapping in the generated layout."""
    skeleton_path = Path(skeleton_path)
    if not skeleton_path.is_file():
        raise PbitBuildError(
            f"skeleton template not found: {skeleton_path} — export one from "
            "Power BI Desktop: File > Export > Power BI template"
        )

    data_path = Path(data_path)
    if not data_path.is_file():
        raise PbitBuildError(f"data payload not found: {data_path}")
    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PbitBuildError(f"could not parse {data_path}: {exc}") from exc

    missing = [key for key in REQUIRED_KEYS if key not in payload]
    if missing:
        raise PbitBuildError(f"payload missing required key(s): {missing}")

    with zipfile.ZipFile(skeleton_path) as z:
        if LAYOUT_PART not in z.namelist():
            raise PbitBuildError(
                f"{skeleton_path} has no {LAYOUT_PART} — is it a Power BI template?"
            )
        parts = [(i, z.read(i.filename)) for i in z.infolist()]
        skeleton_layout = json.loads(z.read(LAYOUT_PART).decode("utf-16-le"))

    layout = layout_for(payload, skeleton_layout)
    encoded = json.dumps(layout, ensure_ascii=False).encode("utf-16-le")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for info, raw in parts:
            name = info.filename
            if name == SECURITY_PART:
                # SecurityBindings binds to the package contents. Rewriting any
                # part invalidates it and Desktop reports the file as corrupted,
                # so it is dropped rather than copied — the same thing every
                # tool that recompiles a pbix/pbit does.
                continue
            if name == CONTENT_TYPES_PART:
                raw = _drop_security_override(raw)
            z.writestr(name, encoded if name == LAYOUT_PART else raw)
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inject the report into a .pbit template")
    parser.add_argument("data", nargs="?", default="output/data.json")
    parser.add_argument("out", nargs="?", default="output/powerbi/SolarEnergyWorldwide.pbit")
    parser.add_argument("skeleton", nargs="?", default=DEFAULT_SKELETON)
    args = parser.parse_args(argv)

    try:
        out = build(Path(args.data), Path(args.out), Path(args.skeleton))
    except PbitBuildError as exc:
        print(f"PBIT BUILD FAILED: {exc}", file=sys.stderr)
        return 1

    layout = json.loads(read_part(out, LAYOUT_PART))
    visuals = sum(len(s["visualContainers"]) for s in layout["sections"])
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    print(f"  {len(layout['sections'])} pages, {visuals} visuals, "
          "model and container copied from the skeleton")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
