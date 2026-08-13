import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js", "render.js", "charts_map.js");
const data = payload();

test("the projection puts null island at the centre", () => {
  assert.deepEqual(S.project(0, 0, 720, 360), { x: 360, y: 180 });
});

test("the projection puts the corners at the corners", () => {
  assert.deepEqual(S.project(90, -180, 720, 360), { x: 0, y: 0 });
  assert.deepEqual(S.project(-90, 180, 720, 360), { x: 720, y: 360 });
});

test("north is up", () => {
  const oslo = S.project(59.91, 10.75, 720, 360);
  const sydney = S.project(-33.87, 151.21, 720, 360);
  assert.ok(oslo.y < sydney.y);
  assert.ok(oslo.x < sydney.x);
});

test("bubble area, not radius, is proportional to the value", () => {
  const big = S.bubbleRadius(100, 100, 0, 10);
  const quarter = S.bubbleRadius(25, 100, 0, 10);
  assert.equal(big, 10);
  assert.equal(quarter, 5);
});

test("a zero value still gets a visible minimum bubble", () => {
  assert.equal(S.bubbleRadius(0, 100, 3, 10), 3);
});

test("a zero maximum does not divide by zero", () => {
  assert.ok(Number.isFinite(S.bubbleRadius(0, 0, 3, 10)));
});

test("every city lands inside the frame", () => {
  const spec = S.mapSpec(data.cities, { width: 720, height: 360 });
  assert.equal(spec.marks.length, 48);
  for (const mark of spec.marks) {
    assert.ok(mark.cx >= 0 && mark.cx <= 720, mark.key + " x");
    assert.ok(mark.cy >= 0 && mark.cy <= 360, mark.key + " y");
  }
});

test("the largest deployment gets the largest bubble", () => {
  const spec = S.mapSpec(data.cities, { width: 720, height: 360 });
  const biggest = spec.marks.slice().sort((a, b) => b.r - a.r)[0];
  const expected = data.cities.slice().sort((a, b) => b.installations - a.installations)[0];
  assert.equal(biggest.key, expected.city);
});

test("bubbles are drawn largest first so small ones stay clickable", () => {
  const spec = S.mapSpec(data.cities, { width: 720, height: 360 });
  const radii = spec.marks.map((m) => m.r);
  assert.deepEqual(radii, radii.slice().sort((a, b) => b - a));
});

test("the graticule spans the frame every thirty degrees", () => {
  const spec = S.mapSpec(data.cities, { width: 720, height: 360 });
  assert.equal(spec.graticule.meridians.length, 13);
  assert.equal(spec.graticule.parallels.length, 7);
});

test("the equator and both tropics are named guides", () => {
  const spec = S.mapSpec(data.cities, { width: 720, height: 360 });
  assert.deepEqual(spec.guides.map((g) => g.label), ["Tropic of Cancer", "Equator", "Tropic of Capricorn"]);
  const equator = spec.guides.find((g) => g.label === "Equator");
  assert.equal(equator.y, 180);
});

test("an empty city list produces a map with a graticule and no bubbles", () => {
  const spec = S.mapSpec([], { width: 720, height: 360 });
  assert.deepEqual(spec.marks, []);
  assert.equal(spec.graticule.meridians.length, 13);
});

test("the map chart is registered on the sustainability page", () => {
  const chart = S.charts.find((c) => c.id === "world-map");
  assert.ok(chart);
  assert.equal(chart.page, "sustainability");
  assert.ok(chart.definition.includes("quirectangular"));
});
