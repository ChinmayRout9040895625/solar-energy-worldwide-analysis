import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load("boot.js", "core.js", "rollup.js");
const data = payload();

const close = (actual, expected, tol, what) =>
  assert.ok(
    Math.abs(actual - expected) <= tol,
    `${what}: ${actual} vs ${expected} (tol ${tol})`
  );

test("round2 keeps two decimals", () => {
  assert.equal(S.round2(26.6449), 26.64);
  assert.equal(S.round2(5), 5);
});

test("groupBy partitions without losing rows", () => {
  const groups = S.groupBy(data.cities, (c) => c.region);
  assert.equal(groups.size, 7);
  let total = 0;
  for (const rows of groups.values()) total += rows.length;
  assert.equal(total, 48);
});

test("consistency is null below three values", () => {
  assert.equal(S.consistencyOf([10000]), null);
  assert.equal(S.consistencyOf([10000, 12000]), null);
});

test("three identical values are genuine perfect consistency", () => {
  assert.equal(S.consistencyOf([10000, 10000, 10000]), 1);
});

test("extreme spread clamps at zero rather than going negative", () => {
  assert.equal(S.consistencyOf([1, 1, 100000]), 0);
});

test("dense rank shares a rank without skipping the next", () => {
  const ranks = S.denseRankDesc([["A", 10], ["B", 10], ["C", 5]]);
  assert.equal(ranks.get("A"), 1);
  assert.equal(ranks.get("B"), 1);
  assert.equal(ranks.get("C"), 2);
});

test("risk counts always carry all three bands", () => {
  const counts = S.riskCountsOf([{ risk_band: "Low" }, { risk_band: "Low" }]);
  assert.deepEqual(counts, { Low: 2, Medium: 0, High: 0 });
});

test("global risk counts match the verified distribution", () => {
  assert.deepEqual(S.riskCountsOf(data.cities), { Low: 5, Medium: 19, High: 24 });
});

test("totals reproduce the Python totals block", () => {
  const t = S.totalsOf(data.cities);
  assert.equal(t.cities, 48);
  assert.equal(t.countries, 30);
  assert.equal(t.regions, 7);
  assert.equal(t.installations, data.totals.installations);
  assert.equal(t.production_kwh, data.totals.production_kwh);
  close(t.co2_tons, data.totals.co2_tons, 1e-9, "totals co2");
});

test("region rollup equals the Python region records field for field", () => {
  const rolled = S.regionRollup(data.cities);
  assert.equal(rolled.length, data.regions.length);
  for (let i = 0; i < rolled.length; i += 1) {
    const got = rolled[i];
    const want = data.regions[i];
    assert.equal(got.region, want.region, "region order");
    assert.equal(got.cities, want.cities);
    assert.equal(got.rank, want.rank);
    assert.equal(got.installations, want.installations);
    assert.equal(got.production_kwh, want.production_kwh);
    assert.equal(got.small_sample, want.small_sample);
    assert.deepEqual(got.risk_counts, want.risk_counts);
    close(got.co2_tons, want.co2_tons, 1e-9, want.region + " co2");
    close(got.mean_roi, want.mean_roi, 0.011, want.region + " mean roi");
    if (want.consistency === null) {
      assert.equal(got.consistency, null, want.region + " consistency");
    } else {
      close(got.consistency, want.consistency, 0.011, want.region + " consistency");
    }
  }
});

test("region rollup is ordered by rank, best first", () => {
  const rolled = S.regionRollup(data.cities);
  assert.equal(rolled[0].region, "Middle East");
  assert.deepEqual(
    rolled.map((r) => r.rank),
    rolled.map((r) => r.rank).slice().sort((a, b) => a - b)
  );
});

test("country rollup equals the Python country records field for field", () => {
  const rolled = S.countryRollup(data.cities);
  assert.equal(rolled.length, data.countries.length);
  for (let i = 0; i < rolled.length; i += 1) {
    const got = rolled[i];
    const want = data.countries[i];
    assert.equal(got.country, want.country, "country order");
    assert.equal(got.region, want.region);
    assert.equal(got.cities, want.cities);
    assert.equal(got.installations, want.installations);
    close(got.co2_tons, want.co2_tons, 1e-9, want.country + " co2");
    close(got.mean_roi, want.mean_roi, 0.011, want.country + " mean roi");
    close(
      got.mean_production_kwh,
      want.mean_production_kwh,
      0.011,
      want.country + " mean production"
    );
  }
});

test("Dubai survives every client-side rollup", () => {
  // The same defect the reference dashboard shipped, guarded on this side too.
  const asia = S.regionRollup(data.cities).find((r) => r.region === "Asia");
  close(asia.co2_tons, 54.72, 1e-9, "Asia co2 including Dubai");
  assert.equal(asia.installations, 1469100);
  const uae = S.countryRollup(data.cities).find((r) => r.country === "UAE");
  close(uae.co2_tons, 6.3, 1e-9, "UAE co2");
  assert.equal(uae.installations, 850);
});

test("filtering to one region still reconciles inside that region", () => {
  const oceania = data.cities.filter((c) => c.region === "Oceania");
  const rolled = S.regionRollup(oceania);
  assert.equal(rolled.length, 1);
  assert.equal(rolled[0].cities, 3);
  assert.equal(rolled[0].rank, 1, "rank is relative to the filtered slice");
  close(
    rolled[0].co2_tons,
    oceania.reduce((sum, c) => sum + c.co2_tons, 0),
    1e-9,
    "Oceania co2"
  );
});

test("an empty selection rolls up to nothing, not to NaN", () => {
  assert.deepEqual(S.regionRollup([]), []);
  assert.deepEqual(S.countryRollup([]), []);
  const t = S.totalsOf([]);
  assert.equal(t.cities, 0);
  assert.equal(t.co2_tons, 0);
});
