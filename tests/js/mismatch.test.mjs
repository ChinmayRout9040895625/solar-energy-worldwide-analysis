import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load(
  "boot.js", "core.js", "rollup.js", "filters.js", "render.js", "charts_mismatch.js"
);
const data = payload();

const OPTS = { width: 700, count: 12, padTop: 40, rowHeight: 22, columnWidth: 210 };

test("each column holds the requested number of cities", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  assert.equal(spec.left.length, 12);
  assert.equal(spec.right.length, 12);
});

test("the left column ranks by installations and the right by ROI", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  const installations = spec.left.map((r) => r.value);
  assert.deepEqual(installations, installations.slice().sort((a, b) => b - a));
  assert.equal(spec.right[0].key, "Phoenix");
  assert.equal(spec.right[1].key, "Dubai");
  assert.equal(spec.right[2].key, "Cairo");
});

test("a link exists only for a city in both columns", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  const leftKeys = new Set(spec.left.map((r) => r.key));
  const rightKeys = new Set(spec.right.map((r) => r.key));
  const both = [...leftKeys].filter((k) => rightKeys.has(k));
  assert.deepEqual(spec.links.map((l) => l.key).sort(), both.sort());
});

test("the two rankings barely overlap — that is the finding", () => {
  // Verified against the CSV: exactly four cities make both top-twelve lists —
  // Los Angeles, Miami, Phoenix and Delhi. The other eight in each column are
  // disjoint, which is what r = 0.137 looks like drawn out.
  const spec = S.mismatchSpec(data.cities, OPTS);
  assert.equal(spec.links.length, 4);
  assert.deepEqual(
    spec.links.map((l) => l.key).sort(),
    ["Delhi", "Los Angeles", "Miami", "Phoenix"]
  );
});

test("rows step down one row height at a time", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  assert.equal(spec.left[1].y - spec.left[0].y, 22);
  assert.equal(spec.left[0].y, 40);
});

test("the columns sit at opposite edges", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  assert.equal(spec.left[0].x, 0);
  assert.equal(spec.right[0].x, 700 - 210);
});

test("each link connects its own two rows", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  for (const link of spec.links) {
    const left = spec.left.find((r) => r.key === link.key);
    const right = spec.right.find((r) => r.key === link.key);
    assert.equal(link.y1, left.y + left.h / 2);
    assert.equal(link.y2, right.y + right.h / 2);
    assert.ok(link.d.startsWith("M"), link.d);
    assert.ok(!link.d.includes("NaN"), link.d);
  }
});

test("fewer cities than the requested count does not overrun", () => {
  const spec = S.mismatchSpec(data.cities.slice(0, 4), OPTS);
  assert.equal(spec.left.length, 4);
  assert.equal(spec.right.length, 4);
});

test("an empty city list produces an empty, valid spec", () => {
  const spec = S.mismatchSpec([], OPTS);
  assert.deepEqual(spec.left, []);
  assert.deepEqual(spec.links, []);
  assert.ok(spec.height > 0);
});

test("the hero is registered first on the financial page", () => {
  const financial = S.charts.filter((c) => c.page === "financial");
  assert.equal(financial[0].id, "mismatch");
});

test("the hero quotes the correlation from the payload", () => {
  const chart = S.charts.find((c) => c.id === "mismatch");
  assert.match(chart.callout({ payload: data }), /0\.137/);
});
