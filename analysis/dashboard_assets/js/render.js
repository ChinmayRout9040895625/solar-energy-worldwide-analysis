/* render.js — element factories and the table-view twin.
   Text always goes in through textContent: series and city names come from a
   CSV and are treated as untrusted data. */
(function (S) {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";

  function applyAttrs(node, attrs) {
    for (const name in attrs) {
      if (!Object.prototype.hasOwnProperty.call(attrs, name)) continue;
      const value = attrs[name];
      if (value === null || value === undefined || value === false) continue;
      if (name === "text") node.textContent = String(value);
      else node.setAttribute(name, value);
    }
  }

  function appendAll(node, children) {
    if (!children) return;
    for (const child of [].concat(children)) {
      if (child) node.appendChild(child);
    }
  }

  // The document is injected rather than read off globalThis, so the node
  // tests can mount the whole page against the shim in tests/js/fakedom.mjs.
  S._doc = null;
  S.useDocument = function (doc) { S._doc = doc; return doc; };
  S.doc = () => S._doc || globalThis.document;

  S.el = function (tag, attrs, children) {
    const node = S.doc().createElement(tag);
    applyAttrs(node, attrs || {});
    appendAll(node, children);
    return node;
  };

  S.svgEl = function (tag, attrs, children) {
    const node = S.doc().createElementNS(SVG_NS, tag);
    applyAttrs(node, attrs || {});
    appendAll(node, children);
    return node;
  };

  S.clear = function (node) {
    node.replaceChildren();
    return node;
  };

  S.drawAxisX = function (spec, format) {
    const group = S.svgEl("g", { class: "axis" });
    const baseline = spec.height - spec.padBottom + 0.5;
    for (const tick of spec.ticks) {
      group.appendChild(S.svgEl("g", { class: "tick" }, [
        S.svgEl("line", {
          x1: tick.x, x2: tick.x, y1: spec.padTop, y2: baseline, class: "gridline",
        }),
        S.svgEl("text", {
          x: tick.x, y: baseline + 16, "text-anchor": "middle", text: format(tick.value),
        }),
      ]));
    }
    group.appendChild(S.svgEl("line", {
      class: "axis-line",
      x1: spec.plotLeft, x2: spec.plotRight, y1: baseline, y2: baseline,
    }));
    return group;
  };

  S.svgRoot = function (spec, label) {
    return S.svgEl("svg", {
      viewBox: "0 0 " + spec.width + " " + spec.height,
      width: spec.width,
      height: spec.height,
      role: "img",
      "aria-label": label,
    });
  };

  S.tipModel = null;  // last model requested, exposed for tests

  S.attachTip = function (node, modelFn) {
    node.addEventListener("pointerenter", () => { S.tipModel = modelFn(); S.showTip(S.tipModel); });
    node.addEventListener("focus", () => { S.tipModel = modelFn(); S.showTip(S.tipModel); });
    node.addEventListener("pointerleave", () => S.hideTip());
    node.addEventListener("blur", () => S.hideTip());
    node.addEventListener("pointermove", (event) => S.moveTip(event));
  };

  S.showTip = function () {};   // replaced in charts_matrix task
  S.hideTip = function () {};
  S.moveTip = function () {};

  S.buildTable = function (model) {
    const head = S.el("thead", null, [
      S.el("tr", null, model.columns.map((c) => S.el("th", { scope: "col", text: c }))),
    ]);
    const body = S.el("tbody", null,
      model.rows.map((row) =>
        S.el("tr", null, row.map((cell, i) =>
          S.el(i === 0 ? "th" : "td", i === 0 ? { scope: "row", text: cell } : { text: cell })
        ))
      )
    );
    return S.el("table", { class: "values" }, [
      S.el("caption", { text: model.caption }),
      head,
      body,
    ]);
  };
})(globalThis.SOLAR);
