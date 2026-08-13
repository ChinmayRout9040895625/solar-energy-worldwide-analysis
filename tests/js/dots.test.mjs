import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js", "render.js", "charts_dots.js");
const data = payload();

const OPTS = { width: 520, labelWidth: 130, valueWidth: 70, padTop: 12, padBottom: 32, band: 26, radius: 5 };

test("dots sit on the value scale", () => {
  const spec = S.dotSpec(
    [{ key: "a", label: "A", value: 0 }, { key: "b", label: "B", value: 10 }],
    Object.assign({ domainMin: 0, domainMax: 10 }, OPTS)
  );
  assert.equal(spec.marks[0].cx, 130);
  assert.equal(spec.marks[1].cx, 450);
});

test("rows are spaced one band apart", () => {
  const rows = ["a", "b", "c"].map((k) => ({ key: k, label: k, value: 1 }));
  const spec = S.dotSpec(rows, Object.assign({ domainMin: 0, domainMax: 2 }, OPTS));
  assert.deepEqual(spec.marks.map((m) => m.cy), [12 + 13, 12 + 39, 12 + 65]);
});

test("markers are at least 8px across", () => {
  const spec = S.dotSpec([{ key: "a", label: "A", value: 1 }], Object.assign({ domainMin: 0, domainMax: 2 }, OPTS));
  assert.ok(spec.marks[0].r >= 4, "radius under 4 gives a marker under 8px");
});

test("a null value is marked missing and carries no coordinate", () => {
  const spec = S.dotSpec(
    [{ key: "a", label: "A", value: null, note: "1 city" }],
    Object.assign({ domainMin: 0, domainMax: 1 }, OPTS)
  );
  assert.equal(spec.marks[0].missing, true);
  assert.equal(spec.marks[0].cx, null);
  assert.equal(spec.marks[0].note, "1 city");
});

test("a domain is derived from the data when not supplied", () => {
  const spec = S.dotSpec(
    [{ key: "a", label: "A", value: 4 }, { key: "b", label: "B", value: 9 }],
    OPTS
  );
  assert.ok(spec.domainMin <= 4 && spec.domainMax >= 9);
});

test("missing values do not drag the domain to zero", () => {
  const spec = S.dotSpec(
    [{ key: "a", label: "A", value: null }, { key: "b", label: "B", value: 9 }],
    OPTS
  );
  assert.ok(spec.domainMin > 0, "a null must not be read as a zero");
});

test("all-missing rows still produce a valid spec", () => {
  const spec = S.dotSpec([{ key: "a", label: "A", value: null }], OPTS);
  assert.equal(spec.marks.length, 1);
  assert.ok(spec.domainMax > spec.domainMin);
});

test("regional consistency reproduces the payload, nulls included", () => {
  const rows = data.regions.map((r) => ({
    key: r.region, label: r.region, value: r.consistency,
  }));
  const spec = S.dotSpec(rows, OPTS);
  const middleEast = spec.marks.find((m) => m.key === "Middle East");
  assert.equal(middleEast.missing, true, "Middle East has one city; consistency is not computable");
  const europe = spec.marks.find((m) => m.key === "Europe");
  assert.equal(europe.missing, false);
});

test("both dot charts are registered with definitions", () => {
  const ids = S.charts.map((c) => c.id);
  assert.ok(ids.includes("regional-roi-rank"));
  assert.ok(ids.includes("production-consistency"));
  for (const chart of S.charts) {
    assert.ok(chart.definition.length > 10, chart.id);
  }
});

test("the consistency table spells out n/a rather than leaving a blank", () => {
  const chart = S.charts.find((c) => c.id === "production-consistency");
  const model = chart.table({ regions: data.regions });
  const middleEast = model.rows.find((row) => row[0] === "Middle East");
  assert.equal(middleEast[2], "n/a");
});
