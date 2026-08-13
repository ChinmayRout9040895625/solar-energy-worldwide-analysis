import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js", "render.js", "charts_scatter.js");
const data = payload();

const OPTS = {
  width: 520, height: 320, padTop: 20, padRight: 20, padBottom: 40, padLeft: 60,
  radius: 5, xDomain: [0, 10], yDomain: [0, 10],
};

const pt = (key, x, y) => ({ key: key, label: key, x: x, y: y, meta: { key: key } });

test("x grows rightward and y grows upward", () => {
  const spec = S.scatterSpec([pt("a", 0, 0), pt("b", 10, 10)], OPTS);
  assert.equal(spec.marks[0].cx, 60);
  assert.equal(spec.marks[0].cy, 280);
  assert.equal(spec.marks[1].cx, 500);
  assert.equal(spec.marks[1].cy, 20);
});

test("the plot box excludes the axis bands", () => {
  const spec = S.scatterSpec([pt("a", 5, 5)], OPTS);
  assert.equal(spec.plotLeft, 60);
  assert.equal(spec.plotRight, 500);
  assert.equal(spec.plotTop, 20);
  assert.equal(spec.plotBottom, 280);
});

test("markers are at least 8px across", () => {
  const spec = S.scatterSpec([pt("a", 5, 5)], OPTS);
  assert.ok(spec.marks[0].r >= 4);
});

test("a derived domain pads the extent so points never sit on the frame", () => {
  const spec = S.scatterSpec([pt("a", 2, 2), pt("b", 8, 8)], { width: 520, height: 320 });
  assert.ok(spec.xDomain[0] < 2 && spec.xDomain[1] > 8);
  assert.ok(spec.yDomain[0] < 2 && spec.yDomain[1] > 8);
});

test("identical values still yield a usable domain", () => {
  const spec = S.scatterSpec([pt("a", 5, 5), pt("b", 5, 5)], { width: 520, height: 320 });
  assert.ok(spec.xDomain[1] > spec.xDomain[0]);
  assert.ok(spec.yDomain[1] > spec.yDomain[0]);
});

test("an empty cloud produces a valid empty spec", () => {
  const spec = S.scatterSpec([], { width: 520, height: 320 });
  assert.deepEqual(spec.marks, []);
  assert.ok(spec.xTicks.length >= 1);
});

test("nearest point wins even when the pointer is nowhere near it", () => {
  const spec = S.scatterSpec([pt("a", 0, 0), pt("b", 10, 10)], OPTS);
  assert.equal(S.nearestMark(spec, 70, 270).key, "a");
  assert.equal(S.nearestMark(spec, 480, 40).key, "b");
});

test("nearest point on an empty cloud is null, not a crash", () => {
  assert.equal(S.nearestMark(S.scatterSpec([], OPTS), 10, 10), null);
});

test("facets share one pair of domains across every panel", () => {
  const points = [pt("a", 1, 1), pt("b", 9, 9), pt("c", 5, 5)];
  points[0].facet = "X";
  points[1].facet = "Y";
  points[2].facet = "X";
  const facets = S.facetSpecs(points, {
    facetOf: (p) => p.facet, width: 520, columns: 2, panelHeight: 140,
  });
  assert.equal(facets.length, 2);
  assert.deepEqual(facets[0].spec.xDomain, facets[1].spec.xDomain);
  assert.deepEqual(facets[0].spec.yDomain, facets[1].spec.yDomain);
});

test("each facet holds its own points and the full context cloud", () => {
  const points = [pt("a", 1, 1), pt("b", 9, 9), pt("c", 5, 5)];
  points[0].facet = "X";
  points[1].facet = "Y";
  points[2].facet = "X";
  const facets = S.facetSpecs(points, {
    facetOf: (p) => p.facet, width: 520, columns: 2, panelHeight: 140,
  });
  const x = facets.find((f) => f.key === "X");
  assert.equal(x.marks.length, 2);
  assert.equal(x.contextMarks.length, 3);
});

test("facets lay out in a grid, left to right then down", () => {
  const points = ["A", "B", "C"].map((k, i) => Object.assign(pt(k, i, i), { facet: k }));
  const facets = S.facetSpecs(points, {
    facetOf: (p) => p.facet, width: 600, columns: 2, panelHeight: 140, gap: 20,
  });
  assert.deepEqual(facets.map((f) => [f.col, f.row]), [[0, 0], [1, 0], [0, 1]]);
  assert.equal(facets[0].x, 0);
  assert.equal(facets[1].x, 310);
  assert.equal(facets[2].y, facets[0].y + 140 + 20);
});

test("the seven regions facet into seven panels", () => {
  const points = data.cities.map((c) => ({
    key: c.city, label: c.city, x: c.ghi, y: c.production_kwh, meta: c,
  }));
  const facets = S.facetSpecs(points, {
    facetOf: (p) => p.meta.region, width: 720, columns: 4, panelHeight: 150,
  });
  assert.equal(facets.length, 7);
  assert.equal(facets.reduce((sum, f) => sum + f.marks.length, 0), 48);
});

test("the three scatter charts are registered", () => {
  const ids = S.charts.map((c) => c.id);
  for (const id of ["installations-vs-roi", "ghi-vs-production", "roi-vs-viability"]) {
    assert.ok(ids.includes(id), "missing " + id);
  }
});

test("the correlation callouts quote the payload, never a recomputed number", () => {
  const ctx = { payload: data, cities: data.cities };
  const chart = S.charts.find((c) => c.id === "installations-vs-roi");
  assert.match(chart.callout(ctx), /0\.137/);
  const viability = S.charts.find((c) => c.id === "roi-vs-viability");
  assert.match(viability.callout(ctx), /0\.982/);
});
