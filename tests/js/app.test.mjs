import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";
import { makeDocument } from "./fakedom.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js", "render.js", "app.js");
const data = payload();

const mountFresh = () => {
  S.charts.length = 0;
  return { doc: makeDocument(data) };
};

test("mount fills the KPI strip from the payload", () => {
  const { doc } = mountFresh();
  S.mount(doc);
  const values = doc
    .getElementById("kpis")
    .querySelectorAll(".kpi-value")
    .map((n) => n.textContent);
  assert.ok(values.includes("48"), values.join(" | "));
  assert.ok(values.some((v) => v.includes("208.35")), values.join(" | "));
});

test("mount renders one chip per region plus one per risk band", () => {
  const { doc } = mountFresh();
  S.mount(doc);
  assert.equal(doc.getElementById("region-chips").querySelectorAll(".chip").length, 7);
  assert.equal(doc.getElementById("risk-chips").querySelectorAll(".chip").length, 3);
});

test("every chip starts selected", () => {
  const { doc } = mountFresh();
  S.mount(doc);
  const chips = doc.getElementById("region-chips").querySelectorAll(".chip");
  assert.ok(chips.every((c) => c.getAttribute("data-selected") === "true"));
});

test("region chips carry a colour key that does not depend on the filter", () => {
  const { doc } = mountFresh();
  const api = S.mount(doc);
  const keyFor = (d) =>
    d.getElementById("region-chips")
      .querySelectorAll(".chip")
      .find((c) => c.textContent.includes("Asia"))
      .querySelector(".chip-key")
      .getAttribute("style");

  const before = keyFor(doc);
  api.setState({ ...api.getState(), regions: ["Asia", "Europe"] });
  assert.equal(keyFor(doc), before, "Asia must keep its hue when others are filtered out");
});

test("mount renders the five caveats", () => {
  const { doc } = mountFresh();
  S.mount(doc);
  assert.equal(doc.getElementById("caveats").querySelectorAll("li").length, 5);
});

test("mount writes the source and generation metadata", () => {
  const { doc } = mountFresh();
  S.mount(doc);
  assert.match(doc.getElementById("meta").textContent, /solar_energy_worldwide\.csv/);
});

test("the readout reports the unfiltered slice on load", () => {
  const { doc } = mountFresh();
  S.mount(doc);
  assert.match(doc.getElementById("filter-readout").textContent, /48 of 48 cities/);
});

test("setState re-renders the readout and the KPI strip", () => {
  const { doc } = mountFresh();
  const api = S.mount(doc);
  api.setState({ ...api.getState(), regions: ["Oceania"] });
  assert.match(doc.getElementById("filter-readout").textContent, /3 of 48 cities/);
  const values = doc
    .getElementById("kpis")
    .querySelectorAll(".kpi-value")
    .map((n) => n.textContent);
  assert.ok(values.includes("3"), values.join(" | "));
});

test("a registered chart gets a card with a title and a definition", () => {
  const { doc } = mountFresh();
  let seen = null;
  S.register({
    id: "probe",
    page: "financial",
    title: "Probe chart",
    definition: "A test measure, defined here.",
    render(container, ctx) { seen = ctx.cities.length; container.appendChild(S.el("g")); },
  });
  S.mount(doc);
  const card = doc.getElementById("page-financial").querySelector(".card");
  assert.ok(card, "card not created");
  assert.match(card.textContent, /Probe chart/);
  assert.match(card.textContent, /A test measure, defined here\./);
  assert.equal(seen, 48);
});

test("a chart re-renders against the filtered slice", () => {
  const { doc } = mountFresh();
  const counts = [];
  S.register({
    id: "probe",
    page: "financial",
    title: "Probe chart",
    definition: "Counts rows.",
    render(container, ctx) { counts.push(ctx.cities.length); },
  });
  const api = S.mount(doc);
  api.setState({ ...api.getState(), bands: ["Low"] });
  assert.deepEqual(counts, [48, 5]);
});

test("charts land on the page they declare", () => {
  const { doc } = mountFresh();
  S.register({ id: "a", page: "production", title: "A", definition: "d", render() {} });
  S.register({ id: "b", page: "sustainability", title: "B", definition: "d", render() {} });
  S.mount(doc);
  assert.equal(doc.getElementById("page-financial").querySelectorAll(".card").length, 0);
  assert.equal(doc.getElementById("page-production").querySelectorAll(".card").length, 1);
  assert.equal(doc.getElementById("page-sustainability").querySelectorAll(".card").length, 1);
});

test("the table twin is built from the chart's own rows", () => {
  const { doc } = mountFresh();
  S.register({
    id: "probe",
    page: "financial",
    title: "Probe",
    definition: "d",
    render() {},
    table(ctx) {
      return {
        caption: "Every city",
        columns: ["City", "ROI %"],
        rows: ctx.cities.map((c) => [c.city, S.fmt1(c.roi_pct)]),
      };
    },
  });
  S.mount(doc);
  const table = doc.getElementById("page-financial").querySelector(".values");
  assert.ok(table, "table twin not built");
  assert.equal(table.querySelectorAll("tbody").length, 1);
  assert.equal(table.querySelector("tbody").querySelectorAll("tr").length, 48);
});

test("mount survives a page with no registered charts", () => {
  const { doc } = mountFresh();
  assert.doesNotThrow(() => S.mount(doc));
});
