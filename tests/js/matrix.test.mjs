import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";
import { makeDocument } from "./fakedom.mjs";

const S = load(
  "boot.js", "core.js", "rollup.js", "filters.js", "render.js", "charts_matrix.js"
);
const data = payload();
S.useDocument(makeDocument(data));

const rows = () => S.matrixRows(data.regions, data.countries, data.cities);

test("the matrix holds every region, country and city exactly once", () => {
  const all = rows();
  assert.equal(all.filter((r) => r.level === 0).length, 7);
  assert.equal(all.filter((r) => r.level === 1).length, 30);
  assert.equal(all.filter((r) => r.level === 2).length, 48);
  assert.equal(all.length, 85);
});

test("countries sit under their own region and cities under their own country", () => {
  const all = rows();
  const byKey = new Map(all.map((r) => [r.key, r]));
  for (const row of all) {
    if (row.level === 0) { assert.equal(row.parent, null); continue; }
    const parent = byKey.get(row.parent);
    assert.ok(parent, row.label + " has no parent row");
    assert.equal(parent.level, row.level - 1);
  }
});

test("a region's children follow it before the next region begins", () => {
  const all = rows();
  const firstRegion = all[0];
  assert.equal(firstRegion.level, 0);
  assert.equal(all[1].parent, firstRegion.key);
});

test("decimals render with a dot, never a space", () => {
  const usa = rows().find((r) => r.label === "United States" && r.level === 1);
  assert.ok(usa.cells.includes("26.64"), usa.cells.join(" | "));
});

test("leaf rows are marked as having no children", () => {
  const all = rows();
  assert.ok(all.filter((r) => r.level === 2).every((r) => r.hasChildren === false));
  assert.ok(all.filter((r) => r.level === 0).every((r) => r.hasChildren === true));
});

test("a single-city region still expands to its one country and city", () => {
  // Middle East holds only Tel Aviv, Israel — Dubai is labelled Asia.
  const all = rows();
  const index = all.findIndex((r) => r.level === 0 && r.label === "Middle East");
  assert.equal(all[index + 1].level, 1);
  assert.equal(all[index + 1].label, "Israel");
  assert.equal(all[index + 2].level, 2);
  assert.equal(all[index + 2].label, "Tel Aviv");
  assert.equal(all[index + 3].level, 0, "the next region begins straight after");
});

test("only region rows are visible before anything is expanded", () => {
  const table = S.drawMatrix(rows(), {});
  const bodyRows = table.querySelectorAll("tr").filter((tr) => tr.getAttribute("data-level"));
  assert.equal(bodyRows.filter((tr) => !tr.hidden).length, 7);
});

test("expanding a region reveals its countries but not their cities", () => {
  const table = S.drawMatrix(rows(), {});
  const all = table.querySelectorAll("tr").filter((tr) => tr.getAttribute("data-level"));
  const europe = all.find((tr) => tr.getAttribute("data-key") === "region:Europe");
  europe.querySelector("button").dispatch("click");

  const visible = all.filter((tr) => !tr.hidden);
  assert.equal(visible.filter((tr) => tr.getAttribute("data-level") === "1").length,
    data.countries.filter((c) => c.region === "Europe").length);
  assert.equal(visible.filter((tr) => tr.getAttribute("data-level") === "2").length, 0);
});

test("collapsing a region hides its descendants again", () => {
  const table = S.drawMatrix(rows(), {});
  const all = table.querySelectorAll("tr").filter((tr) => tr.getAttribute("data-level"));
  const europe = all.find((tr) => tr.getAttribute("data-key") === "region:Europe");
  europe.querySelector("button").dispatch("click");
  europe.querySelector("button").dispatch("click");
  assert.equal(all.filter((tr) => !tr.hidden).length, 7);
});

test("the expand control reports its state to assistive technology", () => {
  const table = S.drawMatrix(rows(), {});
  const europe = table
    .querySelectorAll("tr")
    .find((tr) => tr.getAttribute("data-key") === "region:Europe");
  const button = europe.querySelector("button");
  assert.equal(button.getAttribute("aria-expanded"), "false");
  button.dispatch("click");
  assert.equal(button.getAttribute("aria-expanded"), "true");
});

test("the matrix chart is registered on the sustainability page", () => {
  const chart = S.charts.find((c) => c.id === "region-country-city");
  assert.ok(chart);
  assert.equal(chart.page, "sustainability");
});
