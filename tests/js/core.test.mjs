import test from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const S = load("boot.js", "core.js");

test("integers carry en-US thousands separators", () => {
  assert.equal(S.fmtInt(2328540), "2,328,540");
  assert.equal(S.fmtInt(150), "150");
});

test("two-decimal formatting uses a dot, never a locale comma", () => {
  // The reference dashboard rendered 26.64 as "26 64".
  assert.equal(S.fmt2(26.64), "26.64");
  assert.equal(S.fmt2(208.35), "208.35");
  assert.equal(S.fmt2(5), "5.00");
});

test("one-decimal formatting rounds half away from zero", () => {
  assert.equal(S.fmt1(17.25), "17.3");
  assert.equal(S.fmt1(6.5), "6.5");
});

test("compact formatting shortens large counts only", () => {
  assert.equal(S.fmtCompact(609000), "609K");
  assert.equal(S.fmtCompact(2328540), "2.3M");
  assert.equal(S.fmtCompact(850), "850");
  assert.equal(S.fmtCompact(9999), "9,999");
});

test("linear scale maps domain ends onto range ends", () => {
  const x = S.linear(0, 100, 20, 220);
  assert.equal(x(0), 20);
  assert.equal(x(100), 220);
  assert.equal(x(50), 120);
});

test("a degenerate domain collapses to the range start", () => {
  const x = S.linear(5, 5, 0, 300);
  assert.equal(x(5), 0);
});

test("nice steps snap to 1, 2, 5 times a power of ten", () => {
  assert.equal(S.niceStep(1), 1);
  assert.equal(S.niceStep(1.4), 2);
  assert.equal(S.niceStep(3), 5);
  assert.equal(S.niceStep(7), 10);
  assert.equal(S.niceStep(230), 500);
});

test("ticks are clean numbers inside the domain", () => {
  assert.deepEqual(S.ticks(0, 20, 4), [0, 5, 10, 15, 20]);
  assert.deepEqual(S.ticks(0, 17.2, 4), [0, 5, 10, 15]);
});

test("a zero-width domain yields a single tick", () => {
  assert.deepEqual(S.ticks(4, 4, 5), [4]);
});

test("floating point does not leak into tick values", () => {
  for (const value of S.ticks(0, 3, 5)) {
    assert.equal(value, Number(value.toFixed(10)));
  }
});

test("extent reads min and max through an accessor", () => {
  const rows = [{ v: 3 }, { v: -1 }, { v: 9 }];
  assert.deepEqual(S.extent(rows, (r) => r.v), [-1, 9]);
});

test("extent of nothing is a zero range", () => {
  assert.deepEqual(S.extent([], (r) => r.v), [0, 0]);
});

test("bar path is square at the baseline and rounded at the data end", () => {
  const d = S.roundedBarPath(10, 0, 100, 12, 4);
  assert.ok(d.startsWith("M10,0"), d);
  assert.ok(d.includes("A4,4"), d);
  assert.ok(d.trim().endsWith("Z"), d);
});

test("a bar shorter than the corner radius does not invert", () => {
  const d = S.roundedBarPath(0, 0, 2, 12, 4);
  assert.ok(!d.includes("NaN"), d);
  assert.ok(!/-\d/.test(d.replace("M0,0", "")), d);
});

test("region colour depends on the name, not the order it arrives in", () => {
  // Callers always pass the FULL region list; the slot must not depend on how
  // that list happens to be ordered, only on which names are in it.
  const one = S.regionColorVar("Asia", ["Europe", "Asia", "Africa"]);
  const two = S.regionColorVar("Asia", ["Africa", "Europe", "Asia"]);
  assert.equal(one, two);
});

test("a duplicated region name does not shift the slots", () => {
  const clean = S.regionColorVar("Europe", ["Africa", "Asia", "Europe"]);
  const dupes = S.regionColorVar("Europe", ["Africa", "Asia", "Asia", "Europe"]);
  assert.equal(clean, dupes);
});

test("every one of the seven regions gets a distinct slot", () => {
  const regions = [
    "Africa", "Asia", "Europe", "Middle East",
    "North America", "Oceania", "South America",
  ];
  const seen = new Set(regions.map((r) => S.regionColorVar(r, regions)));
  assert.equal(seen.size, 7);
});

test("slot list is the seven validated categorical slots", () => {
  assert.equal(S.REGION_SLOTS.length, 7);
  assert.deepEqual(S.REGION_SLOTS.slice(0, 2), ["--series-1", "--series-2"]);
});
