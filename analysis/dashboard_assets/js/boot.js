/* boot.js — namespace and payload access. First asset in ASSET_ORDER. */
globalThis.SOLAR = globalThis.SOLAR || {};

(function (S) {
  "use strict";

  S.readPayload = function (doc) {
    const node = (doc || globalThis.document).getElementById("solar-data");
    if (!node) throw new Error("solar-data payload block missing");
    return JSON.parse(node.textContent);
  };
})(globalThis.SOLAR);
