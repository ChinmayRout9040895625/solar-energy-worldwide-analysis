/* page.test.mjs — the whole page, assembled.
   Every other JS test checks one module in isolation; this one loads the same
   modules in the same order as ASSET_ORDER and mounts them, so a runtime error
   in any render path fails here rather than silently in a browser. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { load, payload, ROOT } from "./load.mjs";
import { makeDocument } from "./fakedom.mjs";

/** The JS load order the build actually ships, read from build_dashboard.py. */
function assetOrder() {
  const source = readFileSync(path.join(ROOT, "analysis", "build_dashboard.py"), "utf8");
  const block = source.slice(source.indexOf("ASSET_ORDER = ("), source.indexOf(")", source.indexOf("ASSET_ORDER = (")));
  return Array.from(block.matchAll(/"js\/([^"]+)"/g)).map((m) => m[1]);
}

const ORDER = assetOrder();
const S = load(...ORDER);
const data = payload();

test("the shipped load order is what these tests exercise", () => {
  assert.equal(ORDER[0], "boot.js");
  assert.equal(ORDER[ORDER.length - 1], "app.js");
});

test("every registered chart renders without throwing", () => {
  const doc = makeDocument(data);
  assert.doesNotThrow(() => S.mount(doc));
});

test("each page host receives a card per chart registered to it", () => {
  const doc = makeDocument(data);
  S.mount(doc);
  let seen = 0;
  for (const page of S.PAGES) {
    const expected = S.charts.filter((c) => c.page === page.id).length;
    const cards = doc.getElementById("page-" + page.id).querySelectorAll(".card");
    assert.equal(cards.length, expected, page.id);
    seen += cards.length;
  }
  assert.equal(seen, S.charts.length);
});

test("every chart draws at least one SVG element", () => {
  const doc = makeDocument(data);
  S.mount(doc);
  for (const chart of S.charts) {
    const card = doc
      .querySelectorAll(".card")
      .find((c) => c.getAttribute("data-chart") === chart.id);
    assert.ok(card, "no card for " + chart.id);
    const svgCount = card.querySelectorAll("svg").length + card.querySelectorAll("table").length;
    assert.ok(svgCount > 0, chart.id + " drew nothing");
  }
});

test("every chart survives an aggressive filter", () => {
  const doc = makeDocument(data);
  const api = S.mount(doc);
  // One region, one band — several charts end up with a single row or none.
  assert.doesNotThrow(() =>
    api.setState({ ...api.getState(), regions: ["Middle East"], bands: ["Low"] })
  );
  assert.doesNotThrow(() =>
    api.setState({ ...api.getState(), regions: ["Middle East"], bands: ["High"] })
  );
});

test("an empty slice still renders every card without throwing", () => {
  const doc = makeDocument(data);
  const api = S.mount(doc);
  api.setState({ ...api.getState(), regions: ["Middle East"], bands: ["High"] });
  assert.match(doc.getElementById("filter-readout").textContent, /0 of 48 cities/);
  assert.equal(doc.querySelectorAll(".card").length, S.charts.length);
});

test("region colour survives filtering — no repaint of the survivors", () => {
  const doc = makeDocument(data);
  const api = S.mount(doc);
  const asiaKey = () =>
    doc.getElementById("region-chips")
      .querySelectorAll(".chip")
      .find((c) => c.textContent.includes("Asia"))
      .querySelector(".chip-key")
      .getAttribute("style");

  const before = asiaKey();
  api.setState({ ...api.getState(), regions: ["Asia", "Oceania"] });
  assert.equal(asiaKey(), before);
});

test("switching pages hides the others", () => {
  const doc = makeDocument(data);
  const api = S.mount(doc);
  api.setState({ ...api.getState(), page: "sustainability" });
  assert.equal(doc.getElementById("page-sustainability").hidden, false);
  assert.equal(doc.getElementById("page-financial").hidden, true);
  assert.equal(doc.getElementById("tab-sustainability").getAttribute("aria-selected"), "true");
});

test("the table twin appears for every chart that declares one", () => {
  const doc = makeDocument(data);
  S.mount(doc);
  const withTables = S.charts.filter((c) => c.table);
  assert.ok(withTables.length > 0);
  for (const chart of withTables) {
    const card = doc
      .querySelectorAll(".card")
      .find((c) => c.getAttribute("data-chart") === chart.id);
    assert.ok(card.querySelector(".values"), chart.id + " has no table twin");
  }
});
