import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js", "render.js", "charts_bars.js");
const data = payload();

const OPTS = { width: 720, labelWidth: 150, valueWidth: 64, padTop: 8, padBottom: 32, thickness: 12, gap: 8 };

test("the longest bar reaches the plot's right edge", () => {
  const spec = S.barSpec([{ key: "a", label: "A", value: 10 }, { key: "b", label: "B", value: 5 }], OPTS);
  assert.equal(spec.plotLeft, 150);
  assert.equal(spec.plotRight, 656);
  assert.equal(spec.marks[0].w, 506);
  assert.equal(spec.marks[1].w, 253);
});

test("bar height accounts for the axis band, not just the bars", () => {
  const spec = S.barSpec([{ key: "a", label: "A", value: 1 }, { key: "b", label: "B", value: 1 }], OPTS);
  assert.equal(spec.height, 8 + 2 * 20 + 32);
});

test("bars stack downward at a constant band", () => {
  const rows = [1, 2, 3].map((n) => ({ key: String(n), label: String(n), value: n }));
  const spec = S.barSpec(rows, OPTS);
  assert.deepEqual(spec.marks.map((m) => m.y), [8, 28, 48]);
  assert.ok(spec.marks.every((m) => m.h === 12));
});

test("a zero value draws no bar and never a negative one", () => {
  const spec = S.barSpec([{ key: "a", label: "A", value: 0 }, { key: "b", label: "B", value: 4 }], OPTS);
  assert.equal(spec.marks[0].w, 0);
});

test("an empty row set produces an empty, valid spec", () => {
  const spec = S.barSpec([], OPTS);
  assert.deepEqual(spec.marks, []);
  assert.equal(spec.height, 40);
  assert.ok(spec.domainMax > 0, "domain must not be zero-width");
});

test("twelve or fewer bars are all labelled", () => {
  const rows = Array.from({ length: 12 }, (_, i) => ({ key: String(i), label: String(i), value: 12 - i }));
  assert.ok(S.barSpec(rows, OPTS).marks.every((m) => m.labelled));
});

test("past twelve bars only the extremes are labelled", () => {
  const rows = Array.from({ length: 48 }, (_, i) => ({ key: String(i), label: String(i), value: 48 - i }));
  const marks = S.barSpec(rows, OPTS).marks;
  assert.deepEqual(marks.map((m) => m.labelled).slice(0, 4), [true, true, true, false]);
  assert.equal(marks[47].labelled, true);
  assert.equal(marks.filter((m) => m.labelled).length, 4);
});

test("a named row is labelled even when it is not an extreme", () => {
  const rows = Array.from({ length: 48 }, (_, i) => ({ key: "c" + i, label: "c" + i, value: 48 - i }));
  const marks = S.barSpec(rows, Object.assign({ alwaysLabel: ["c20"] }, OPTS)).marks;
  assert.equal(marks[20].labelled, true);
});

test("ticks are clean and land inside the plot", () => {
  const spec = S.barSpec([{ key: "a", label: "A", value: 17.2 }], OPTS);
  assert.ok(spec.ticks.length >= 3);
  for (const tick of spec.ticks) {
    assert.ok(tick.x >= spec.plotLeft - 1e-9 && tick.x <= spec.plotRight + 1e-9);
  }
});

const STACK_OPTS = { width: 560, labelWidth: 120, valueWidth: 48, padTop: 8, padBottom: 32, thickness: 14, gap: 10, segGap: 2, minLabelWidth: 24 };
const BANDS = ["Low", "Medium", "High"];

test("stacked segments run left to right in band order", () => {
  const spec = S.stackSpec([{ key: "A", label: "A", parts: { Low: 1, Medium: 1, High: 2 } }], BANDS, STACK_OPTS);
  const segments = spec.marks[0].segments;
  assert.deepEqual(segments.map((s) => s.key), BANDS);
  assert.deepEqual(segments.map((s) => s.x), [120, 218, 316]);
});

test("a 2px surface gap separates every segment except the last", () => {
  const spec = S.stackSpec([{ key: "A", label: "A", parts: { Low: 1, Medium: 1, High: 2 } }], BANDS, STACK_OPTS);
  const segments = spec.marks[0].segments;
  assert.deepEqual(segments.map((s) => s.w), [96, 96, 196]);
});

test("the full stack ends exactly at the plot's right edge", () => {
  const spec = S.stackSpec([{ key: "A", label: "A", parts: { Low: 1, Medium: 1, High: 2 } }], BANDS, STACK_OPTS);
  const last = spec.marks[0].segments[2];
  assert.equal(last.x + last.w, spec.plotRight);
});

test("an empty band still gets a segment, with zero width and no label", () => {
  const spec = S.stackSpec([{ key: "A", label: "A", parts: { Low: 0, Medium: 2, High: 0 } }], BANDS, STACK_OPTS);
  const segments = spec.marks[0].segments;
  assert.equal(segments.length, 3);
  assert.equal(segments[0].w, 0);
  assert.equal(segments[0].labelled, false);
});

test("a segment too narrow for its number is not labelled inside", () => {
  const spec = S.stackSpec([{ key: "A", label: "A", parts: { Low: 1, Medium: 99, High: 0 } }], BANDS, STACK_OPTS);
  assert.equal(spec.marks[0].segments[0].labelled, false, "1 of 100 cannot hold a label");
  assert.equal(spec.marks[0].segments[1].labelled, true);
});

test("stack totals match the region risk counts from the payload", () => {
  const rows = data.regions.map((r) => ({
    key: r.region, label: r.region, parts: r.risk_counts,
  }));
  const spec = S.stackSpec(rows, BANDS, STACK_OPTS);
  assert.deepEqual(spec.marks.map((m) => m.total), data.regions.map((r) => r.cities));
  assert.equal(spec.marks.reduce((sum, m) => sum + m.total, 0), 48);
});

test("every bar chart in the registry declares a definition", () => {
  assert.ok(S.charts.length >= 5);
  for (const chart of S.charts) {
    assert.ok(chart.definition && chart.definition.length > 10, chart.id);
    assert.ok(chart.title, chart.id);
    assert.ok(["financial", "production", "sustainability"].includes(chart.page), chart.id);
  }
});

test("the registered charts include the five bar charts by id", () => {
  const ids = S.charts.map((c) => c.id);
  for (const id of ["roi-by-city", "risk-by-region", "production-by-country", "installations-by-region", "co2-by-country"]) {
    assert.ok(ids.includes(id), "missing " + id);
  }
});
