/* boot.js — namespace and payload access. First asset in ASSET_ORDER. */
globalThis.SOLAR = globalThis.SOLAR || {};

(function (S) {
  "use strict";

  // The chart registry lives here, not in app.js: chart modules register at
  // load time and app.js is deliberately LAST in ASSET_ORDER, so a registry
  // defined there would not exist yet when the charts loaded.
  S.charts = [];
  S.register = function (chart) { S.charts.push(chart); };

  S.readPayload = function (doc) {
    const node = (doc || globalThis.document).getElementById("solar-data");
    if (!node) throw new Error("solar-data payload block missing");
    return JSON.parse(node.textContent);
  };
})(globalThis.SOLAR);
