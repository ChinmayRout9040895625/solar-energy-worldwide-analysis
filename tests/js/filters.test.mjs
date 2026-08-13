import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js");
const data = payload();

const REGIONS = Array.from(new Set(data.cities.map((c) => c.region))).sort();
const BANDS = ["Low", "Medium", "High"];

test("the initial state selects everything", () => {
  const state = S.initialState(data);
  assert.deepEqual(state.regions, REGIONS);
  assert.deepEqual(state.bands, BANDS);
  assert.equal(state.page, "financial");
  assert.equal(S.filterCities(data.cities, state).length, 48);
});

test("toggling a value off removes only that value", () => {
  const next = S.toggleValue(REGIONS, "Europe", REGIONS);
  assert.ok(!next.includes("Europe"));
  assert.equal(next.length, REGIONS.length - 1);
});

test("toggling the same value back on restores it", () => {
  const off = S.toggleValue(REGIONS, "Europe", REGIONS);
  const on = S.toggleValue(off, "Europe", REGIONS);
  assert.deepEqual(on, REGIONS);
});

test("emptying the selection restores all rather than blanking the page", () => {
  const next = S.toggleValue(["Europe"], "Europe", REGIONS);
  assert.deepEqual(next, REGIONS);
});

test("isolate narrows to a single value", () => {
  assert.deepEqual(S.isolateValue(REGIONS, "Asia", REGIONS), ["Asia"]);
});

test("isolating an already-isolated value restores all", () => {
  assert.deepEqual(S.isolateValue(["Asia"], "Asia", REGIONS), REGIONS);
});

test("region filtering keeps the right cities", () => {
  const state = { ...S.initialState(data), regions: ["Oceania"] };
  const rows = S.filterCities(data.cities, state);
  assert.equal(rows.length, 3);
  assert.ok(rows.every((c) => c.region === "Oceania"));
});

test("risk filtering keeps the right cities", () => {
  const state = { ...S.initialState(data), bands: ["Low"] };
  assert.equal(S.filterCities(data.cities, state).length, 5);
});

test("region and risk filters intersect", () => {
  const state = { ...S.initialState(data), regions: ["Asia"], bands: ["Low"] };
  const rows = S.filterCities(data.cities, state);
  assert.ok(rows.every((c) => c.region === "Asia" && c.risk_band === "Low"));
  assert.ok(rows.some((c) => c.city === "Dubai"), "Dubai is Asia and Low");
});

test("a filter that matches nothing yields an empty list, not an error", () => {
  const state = { ...S.initialState(data), regions: ["Middle East"], bands: ["High"] };
  assert.deepEqual(S.filterCities(data.cities, state), []);
});

test("the readout names the slice in plain words", () => {
  const state = S.initialState(data);
  const all = S.describeFilter(data.cities, data.cities, state, REGIONS, BANDS);
  assert.match(all, /48 of 48 cities/);
  assert.match(all, /all regions/);

  const narrowed = { ...state, regions: ["Asia"] };
  const rows = S.filterCities(data.cities, narrowed);
  const text = S.describeFilter(data.cities, rows, narrowed, REGIONS, BANDS);
  assert.match(text, /12 of 48 cities/);
  assert.match(text, /Asia/);
});
