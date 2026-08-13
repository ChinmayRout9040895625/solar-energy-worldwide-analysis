/* charts_dots.js — ordered dot plots.
   A null value is not a zero and not a one: it is rendered as words. */
(function (S) {
  "use strict";

  const DOT_DEFAULTS = {
    width: 520, labelWidth: 130, valueWidth: 70,
    padTop: 12, padBottom: 32, band: 26, radius: 5, tickCount: 4,
  };

  S.dotSpec = function (rows, options) {
    const o = Object.assign({}, DOT_DEFAULTS, options || {});
    const plotLeft = o.labelWidth;
    const plotRight = o.width - o.valueWidth;
    const present = rows.filter((r) => r.value !== null && r.value !== undefined);

    let domainMin = o.domainMin;
    let domainMax = o.domainMax;
    if (domainMin === undefined || domainMax === undefined) {
      const values = present.map((r) => r.value);
      const lo = values.length ? Math.min.apply(null, values) : 0;
      const hi = values.length ? Math.max.apply(null, values) : 1;
      const pad = (hi - lo) * 0.15 || Math.max(Math.abs(hi) * 0.1, 1);
      if (domainMin === undefined) domainMin = lo - pad;
      if (domainMax === undefined) domainMax = hi + pad;
    }
    if (!(domainMax > domainMin)) domainMax = domainMin + 1;

    const x = S.linear(domainMin, domainMax, plotLeft, plotRight);
    const marks = rows.map(function (row, i) {
      const missing = row.value === null || row.value === undefined;
      return {
        key: row.key,
        label: row.label,
        value: row.value,
        note: row.note || null,
        meta: row.meta || null,
        missing: missing,
        cx: missing ? null : x(row.value),
        cy: o.padTop + i * o.band + o.band / 2,
        r: o.radius,
      };
    });

    return {
      marks: marks,
      ticks: S.ticks(domainMin, domainMax, o.tickCount).map((v) => ({ value: v, x: x(v) })),
      width: o.width,
      height: o.padTop + rows.length * o.band + o.padBottom,
      padTop: o.padTop,
      padBottom: o.padBottom,
      plotLeft: plotLeft,
      plotRight: plotRight,
      domainMin: domainMin,
      domainMax: domainMax,
    };
  };

  S.drawDots = function (spec, options) {
    const o = options || {};
    const svg = S.svgRoot(spec, o.ariaLabel || "Dot plot");
    svg.appendChild(S.drawAxisX(spec, o.tickFormat || S.fmt1));

    for (const mark of spec.marks) {
      const group = S.svgEl("g", { class: "mark", "data-key": mark.key });
      group.appendChild(S.svgEl("text", {
        class: "cat-label",
        x: spec.plotLeft - 10, y: mark.cy + 4, "text-anchor": "end", text: mark.label,
      }));

      if (mark.missing) {
        group.appendChild(S.svgEl("text", {
          class: "note",
          x: spec.plotLeft + 4, y: mark.cy + 4,
          text: "n/a — " + (mark.note || "not computable"),
        }));
      } else {
        // 2px surface ring keeps overlapping dots legible.
        group.appendChild(S.svgEl("circle", {
          cx: mark.cx, cy: mark.cy, r: mark.r + 2, fill: "var(--surface-1)",
        }));
        group.appendChild(S.svgEl("circle", {
          cx: mark.cx, cy: mark.cy, r: mark.r,
          fill: o.colorOf ? o.colorOf(mark) : "var(--series-1)",
        }));
        group.appendChild(S.svgEl("text", {
          class: "value-label",
          x: spec.plotRight + 10, y: mark.cy + 4,
          text: (o.valueFormat || S.fmt2)(mark.value) + (mark.note ? " · " + mark.note : ""),
        }));
      }

      const hit = S.svgEl("rect", {
        class: "hit",
        x: 0, y: mark.cy - 13, width: spec.width, height: 26,
        tabindex: "0",
        role: o.onSelect ? "button" : null,
        "aria-label": o.ariaFor(mark),
      });
      S.attachTip(hit, () => o.tip(mark));
      if (o.onSelect) {
        hit.addEventListener("click", () => o.onSelect(mark));
        hit.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") o.onSelect(mark);
        });
      }
      group.appendChild(hit);
      svg.appendChild(group);
    }
    return svg;
  };

  S.register({
    id: "regional-roi-rank",
    page: "financial",
    title: "Regional ROI ranking",
    definition:
      "Dense rank on mean ROI_Percentage, highest first — tied regions share a " +
      "rank and the next is not skipped. Regions under five cities are marked.",
    render: function (container, ctx) {
      const rows = ctx.regions.map((r) => ({
        key: r.region,
        label: "#" + r.rank + "  " + r.region,
        value: r.mean_roi,
        note: r.small_sample ? "n=" + r.cities : null,
        meta: r,
      }));
      container.appendChild(S.drawDots(S.dotSpec(rows, { width: 540, labelWidth: 150 }), {
        ariaLabel: "Mean return on investment by region, best rank first",
        valueFormat: (v) => S.fmt2(v) + "%",
        tickFormat: (v) => S.fmt1(v) + "%",
        colorOf: (mark) => S.regionColorVar(mark.key, ctx.allRegions),
        ariaFor: (mark) => mark.label + ": " + S.fmt2(mark.value) + "% mean ROI",
        onSelect: (mark) => ctx.isolate("regions", mark.key),
        tip: (mark) => ({
          value: S.fmt2(mark.value) + "% mean ROI",
          label: mark.meta.region + " · rank " + mark.meta.rank,
          rows: [
            ["Cities", S.fmtInt(mark.meta.cities)],
            ["Installations", S.fmtInt(mark.meta.installations)],
          ],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Mean ROI by region",
      columns: ["Region", "Rank", "Mean ROI %", "Cities"],
      rows: ctx.regions.map((r) => [
        r.region, String(r.rank), S.fmt2(r.mean_roi), S.fmtInt(r.cities),
      ]),
    }),
  });

  S.register({
    id: "production-consistency",
    page: "production",
    title: "Production consistency by region",
    definition:
      "1 − (σ ÷ μ) of Avg_Annual_Production_kWh within a region, sample σ, clamped " +
      "to 0–1. Not computable under three cities: one city has no spread, which " +
      "would otherwise read as perfect consistency.",
    render: function (container, ctx) {
      const rows = ctx.regions
        .slice()
        .sort((a, b) => (b.consistency === null ? -1 : b.consistency) - (a.consistency === null ? -1 : a.consistency))
        .map((r) => ({
          key: r.region,
          label: r.region,
          value: r.consistency,
          note: r.consistency === null
            ? r.cities + (r.cities === 1 ? " city" : " cities")
            : (r.small_sample ? "n=" + r.cities : null),
          meta: r,
        }));
      container.appendChild(S.drawDots(S.dotSpec(rows, { width: 540, labelWidth: 130, domainMin: 0, domainMax: 1 }), {
        ariaLabel: "Production consistency by region",
        valueFormat: S.fmt2,
        tickFormat: S.fmt2,
        colorOf: (mark) => S.regionColorVar(mark.key, ctx.allRegions),
        ariaFor: (mark) => mark.missing
          ? mark.label + ": not computable, " + mark.note
          : mark.label + ": consistency " + S.fmt2(mark.value),
        onSelect: (mark) => ctx.isolate("regions", mark.key),
        tip: (mark) => ({
          value: mark.missing ? "n/a" : S.fmt2(mark.value),
          label: mark.label + (mark.missing ? " — needs 3+ cities" : " production consistency"),
          rows: [
            ["Cities", S.fmtInt(mark.meta.cities)],
            ["Production", S.fmtInt(mark.meta.production_kwh) + " kWh/yr"],
          ],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Production consistency by region",
      columns: ["Region", "Cities", "Consistency"],
      rows: ctx.regions.map((r) => [
        r.region, S.fmtInt(r.cities), r.consistency === null ? "n/a" : S.fmt2(r.consistency),
      ]),
    }),
  });
})(globalThis.SOLAR);
