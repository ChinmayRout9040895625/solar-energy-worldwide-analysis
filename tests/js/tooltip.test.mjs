import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";
import { makeDocument } from "./fakedom.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js", "render.js");
const doc = makeDocument(payload());
S.useDocument(doc);

test("the tooltip element is created once and reused", () => {
  const first = S.ensureTip();
  const second = S.ensureTip();
  assert.equal(first, second);
  assert.equal(doc.body.querySelectorAll(".tooltip").length, 1);
});

test("the value leads and the label follows", () => {
  S.showTip({ value: "17.2% ROI", label: "Phoenix, United States", rows: [] });
  const tip = S.ensureTip();
  assert.match(tip.querySelector(".tip-value").textContent, /17\.2% ROI/);
  assert.match(tip.querySelector(".tip-label").textContent, /Phoenix/);
});

test("detail rows render as label and value pairs", () => {
  S.showTip({
    value: "6.30 t", label: "Dubai",
    rows: [["Region", "Asia"], ["Installations", "850"]],
  });
  const tip = S.ensureTip();
  assert.equal(tip.querySelectorAll(".tip-row").length, 2);
  assert.match(tip.textContent, /Installations/);
  assert.match(tip.textContent, /850/);
});

test("labels go in as text, never as markup", () => {
  S.showTip({ value: "1", label: "<img onerror=alert(1)>", rows: [] });
  const tip = S.ensureTip();
  assert.equal(tip.querySelector(".tip-label").textContent, "<img onerror=alert(1)>");
  assert.equal(tip.querySelectorAll("img").length, 0);
});

test("showing then hiding leaves the tooltip hidden", () => {
  S.showTip({ value: "1", label: "x", rows: [] });
  assert.equal(S.ensureTip().hidden, false);
  S.hideTip();
  assert.equal(S.ensureTip().hidden, true);
});

test("a tooltip with no detail rows still renders", () => {
  assert.doesNotThrow(() => S.showTip({ value: "1", label: "x" }));
});
