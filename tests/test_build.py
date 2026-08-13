import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.build_dashboard import (
    ALLOWED_URL_LITERALS,
    ASSET_ORDER,
    DashboardBuildError,
    assert_self_contained,
    build,
    embed_json,
    render_html,
    main,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "output" / "data.json"
ASSETS = ROOT / "analysis" / "dashboard_assets"


@pytest.fixture(scope="module")
def payload() -> dict:
    if not DATA.is_file():
        pytest.fail("output/data.json missing — run `python -m analysis.build_data`")
    return json.loads(DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def html(payload) -> str:
    return render_html(payload)


def test_every_declared_asset_exists():
    missing = [name for name in ASSET_ORDER if not (ASSETS / name).is_file()]
    assert missing == []


def test_shell_declares_all_three_slots():
    shell = (ASSETS / "shell.html").read_text(encoding="utf-8")
    for slot in ("{{CSS}}", "{{JS}}", "{{DATA}}"):
        assert slot in shell


def test_no_slot_survives_rendering(html):
    for slot in ("{{CSS}}", "{{JS}}", "{{DATA}}"):
        assert slot not in html


def test_html_has_no_external_references(html):
    assert_self_contained(html)  # must not raise


def test_scanner_rejects_a_stylesheet_link():
    with pytest.raises(DashboardBuildError) as excinfo:
        assert_self_contained('<link rel="stylesheet" href="x.css">')
    assert "link" in str(excinfo.value).lower()


def test_scanner_rejects_an_https_url():
    with pytest.raises(DashboardBuildError) as excinfo:
        assert_self_contained("<p>see https://example.com/x.png</p>")
    assert "https://example.com" in str(excinfo.value)


def test_scanner_rejects_a_protocol_relative_url():
    with pytest.raises(DashboardBuildError):
        assert_self_contained('<script src="//cdn.example.com/x.js"></script>')


def test_scanner_rejects_a_css_import():
    with pytest.raises(DashboardBuildError):
        assert_self_contained("<style>@import 'other.css';</style>")


def test_scanner_rejects_a_remote_css_url():
    with pytest.raises(DashboardBuildError):
        assert_self_contained("<style>body{background:url(bg.png)}</style>")


def test_scanner_allows_a_data_uri():
    assert_self_contained("<style>body{background:url(data:image/gif;base64,R0lGOD)}</style>")


def test_scanner_allows_the_svg_namespace_literal():
    # createElementNS needs this exact string; it is an identifier, not a fetch.
    assert_self_contained('<script>const NS="http://www.w3.org/2000/svg";</script>')


def test_allowed_literals_are_namespaces_only():
    assert set(ALLOWED_URL_LITERALS) == {
        "http://www.w3.org/2000/svg",
        "http://www.w3.org/1999/xlink",
    }


def test_payload_is_embedded_and_parseable(html):
    start = html.index('<script type="application/json" id="solar-data">')
    start = html.index(">", start) + 1
    end = html.index("</script>", start)
    embedded = json.loads(html[start:end])
    assert len(embedded["cities"]) == 48
    assert embedded["totals"]["installations"] == 2328540


def test_embedded_json_cannot_close_the_script_tag(payload):
    hostile = dict(payload)
    hostile["caveats"] = ["</script><img onerror=alert(1)>"]
    assert "</script>" not in embed_json(hostile)
    assert "\\u003c" in embed_json(hostile)


def test_every_js_asset_is_inlined(html):
    for name in ASSET_ORDER:
        if name.endswith(".js"):
            source = (ASSETS / name).read_text(encoding="utf-8")
            probe = next(line for line in source.splitlines() if line.strip())
            assert probe.strip() in html


def test_css_is_inlined(html):
    assert "--series-1" in html
    assert "<style>" in html


def test_html_carries_no_link_or_script_src(html):
    assert "<link" not in html.lower()
    assert "src=" not in html.lower()


def test_three_tab_panels_are_present(html):
    for page in ("page-financial", "page-production", "page-sustainability"):
        assert f'id="{page}"' in html


def test_caveats_are_rendered_from_the_data(payload, html):
    assert len(payload["caveats"]) == 5
    for caveat in payload["caveats"]:
        fragment = caveat.split(".")[0][:40]
        assert fragment in html


def test_title_names_the_project(html):
    assert "<title>" in html
    assert "Solar" in html


def test_build_writes_the_file(tmp_path):
    out = tmp_path / "dashboard.html"
    html = build(DATA, out)
    assert out.exists()
    assert out.read_text(encoding="utf-8") == html


def test_build_creates_missing_parent_directory(tmp_path):
    out = tmp_path / "nested" / "deeper" / "dashboard.html"
    build(DATA, out)
    assert out.exists()


def test_build_raises_on_missing_data_json(tmp_path):
    with pytest.raises(DashboardBuildError) as excinfo:
        build(tmp_path / "absent.json", tmp_path / "dashboard.html")
    assert "absent.json" in str(excinfo.value)


def test_build_raises_on_malformed_data_json(tmp_path):
    broken = tmp_path / "data.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(DashboardBuildError):
        build(broken, tmp_path / "dashboard.html")


def test_build_raises_when_a_required_key_is_missing(tmp_path, payload):
    trimmed = {k: v for k, v in payload.items() if k != "cities"}
    path = tmp_path / "data.json"
    path.write_text(json.dumps(trimmed), encoding="utf-8")
    with pytest.raises(DashboardBuildError) as excinfo:
        build(path, tmp_path / "dashboard.html")
    assert "cities" in str(excinfo.value)


def test_failed_build_writes_nothing(tmp_path):
    out = tmp_path / "dashboard.html"
    with pytest.raises(DashboardBuildError):
        build(tmp_path / "absent.json", out)
    assert not out.exists()


def test_main_returns_zero_on_success(tmp_path):
    assert main([str(DATA), str(tmp_path / "dashboard.html")]) == 0


def test_main_returns_one_on_failure(tmp_path):
    assert main([str(tmp_path / "absent.json"), str(tmp_path / "dashboard.html")]) == 1


def test_asset_order_ends_with_app_js():
    assert ASSET_ORDER[-1] == "js/app.js"


def test_chart_modules_load_before_the_app(html):
    assert html.index("S.mount = function") > html.index("S.filterCities = function")


def test_page_hosts_are_empty_in_the_emitted_html(html):
    # Cards are built at runtime from the registry; the shell ships them empty.
    start = html.index('id="page-financial"')
    end = html.index("</section>", start)
    assert "card" not in html[start:end]
