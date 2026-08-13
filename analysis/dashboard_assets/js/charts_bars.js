/* charts_bars.js — ranked horizontal bars and the stacked risk chart.
   Geometry is pure (barSpec, stackSpec); drawing is a thin pass over it. */
(function (S) {
  "use strict";

  const BAR_DEFAULTS = {
    width: 720, labelWidth: 150, valueWidth: 64,
    padTop: 8, padBottom: 32, thickness: 12, gap: 8,
    tickCount: 5, labelTop: 3, labelBottom: 1, alwaysLabel: [],
  };

  const STACK_DEFAULTS = {
    width: 560, labelWidth: 120, valueWidth: 48,
    padTop: 8, padBottom: 32, thickness: 14, gap: 10,
    segGap: 2, minLabelWidth: 24, tickCount: 4,
  };

  S.barSpec = function (rows, options) {
    const o = Object.assign({}, BAR_DEFAULTS, options || {});
    const plotLeft = o.labelWidth;
    const plotRight = o.width - o.valueWidth;
    const domainMax = rows.length ? Math.max.apply(null, rows.map((r) => r.value)) : 0;
    const domain = domainMax > 0 ? domainMax : 1;
    const x = S.linear(0, domain, plotLeft, plotRight);
    const band = o.thickness + o.gap;
    const dense = rows.length > 12;

    const marks = rows.map(function (row, i) {
      const named = o.alwaysLabel.indexOf(row.key) >= 0;
      const extreme = i < o.labelTop || i >= rows.length - o.labelBottom;
      return {
        key: row.key,
        label: row.label,
        value: row.value,
        meta: row.meta || null,
        x: plotLeft,
        y: o.padTop + i * band,
        w: Math.max(0, x(row.value) - plotLeft),
        h: o.thickness,
        labelled: !dense || extreme || named,
      };
    });

    return {
      marks: marks,
      ticks: S.ticks(0, domain, o.tickCount).map((v) => ({ value: v, x: x(v) })),
      width: o.width,
      height: o.padTop + rows.length * band + o.padBottom,
      padTop: o.padTop,
      padBottom: o.padBottom,
      plotLeft: plotLeft,
      plotRight: plotRight,
      domainMax: domain,
    };
  };

  S.stackSpec = function (rows, keys, options) {
    const o = Object.assign({}, STACK_DEFAULTS, options || {});
    const plotLeft = o.labelWidth;
    const plotRight = o.width - o.valueWidth;
    const span = plotRight - plotLeft;
    const totals = rows.map((r) => keys.reduce((sum, k) => sum + (r.parts[k] || 0), 0));
    const domainMax = totals.length ? Math.max.apply(null, totals) : 0;
    const domain = domainMax > 0 ? domainMax : 1;
    const band = o.thickness + o.gap;

    const marks = rows.map(function (row, i) {
      const total = totals[i];
      let lastFilled = -1;
      keys.forEach((k, j) => { if ((row.parts[k] || 0) > 0) lastFilled = j; });

      let cursor = plotLeft;
      const segments = keys.map(function (key, j) {
        const value = row.parts[key] || 0;
        const raw = (value / domain) * span;
        const width = value === 0 ? 0 : j === lastFilled ? raw : Math.max(0, raw - o.segGap);
        const segment = {
          key: key,
          value: value,
          x: cursor,
          w: width,
          labelled: raw >= o.minLabelWidth,
        };
        cursor += raw;
        return segment;
      });

      return {
        key: row.key,
        label: row.label,
        total: total,
        meta: row.meta || null,
        y: o.padTop + i * band,
        h: o.thickness,
        segments: segments,
      };
    });

    return {
      marks: marks,
      ticks: S.ticks(0, domain, o.tickCount).map((v) => ({ value: v, x: plotLeft + (v / domain) * span })),
      width: o.width,
      height: o.padTop + rows.length * band + o.padBottom,
      padTop: o.padTop,
      padBottom: o.padBottom,
      plotLeft: plotLeft,
      plotRight: plotRight,
      domainMax: domain,
    };
  };

  S.drawBars = function (spec, options) {
    const o = options || {};
    const svg = S.svgRoot(spec, o.ariaLabel || "Bar chart");
    svg.appendChild(S.drawAxisX(spec, o.tickFormat || S.fmtCompact));

    for (const mark of spec.marks) {
      const color = o.colorOf ? o.colorOf(mark) : "var(--series-1)";
      const group = S.svgEl("g", { class: "mark", "data-key": mark.key });

      group.appendChild(S.svgEl("text", {
        class: "cat-label",
        x: spec.plotLeft - 10,
        y: mark.y + mark.h - 1,
        "text-anchor": "end",
        text: mark.label,
      }));

      group.appendChild(S.svgEl("path", {
        d: S.roundedBarPath(mark.x, mark.y, mark.w, mark.h, 4),
        fill: color,
      }));

      if (mark.labelled) {
        group.appendChild(S.svgEl("text", {
          class: "value-label",
          x: mark.x + mark.w + 8,
          y: mark.y + mark.h - 1,
          text: (o.valueFormat || S.fmtCompact)(mark.value),
        }));
      }

      // Hit target spans the whole band, never just the painted pixels.
      const hit = S.svgEl("rect", {
        class: "hit",
        x: 0, y: mark.y - 4, width: spec.width, height: mark.h + 8,
        tabindex: "0",
        role: o.onSelect ? "button" : null,
        "aria-label": mark.label + ": " + (o.valueFormat || S.fmtCompact)(mark.value),
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

  S.drawStack = function (spec, keys, options) {
    const o = options || {};
    const svg = S.svgRoot(spec, o.ariaLabel || "Stacked bar chart");
    svg.appendChild(S.drawAxisX(spec, o.tickFormat || S.fmtInt));

    for (const mark of spec.marks) {
      const group = S.svgEl("g", { class: "mark", "data-key": mark.key });
      group.appendChild(S.svgEl("text", {
        class: "cat-label",
        x: spec.plotLeft - 10,
        y: mark.y + mark.h - 2,
        "text-anchor": "end",
        text: mark.label,
      }));

      for (const segment of mark.segments) {
        if (segment.w <= 0) continue;
        group.appendChild(S.svgEl("rect", {
          x: segment.x, y: mark.y, width: segment.w, height: mark.h,
          fill: o.colorOf(segment.key), rx: 2,
        }));
        if (segment.labelled) {
          group.appendChild(S.svgEl("text", {
            class: "seg-label",
            x: segment.x + segment.w / 2,
            y: mark.y + mark.h - 3,
            "text-anchor": "middle",
            fill: o.inkOn(segment.key),
            text: S.fmtInt(segment.value),
          }));
        }
      }

      group.appendChild(S.svgEl("text", {
        class: "value-label",
        x: spec.plotRight + 8,
        y: mark.y + mark.h - 2,
        text: S.fmtInt(mark.total),
      }));

      const hit = S.svgEl("rect", {
        class: "hit",
        x: 0, y: mark.y - 4, width: spec.width, height: mark.h + 8,
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

  const RISK_COLOR = {
    Low: "var(--status-good)",
    Medium: "var(--status-warning)",
    High: "var(--status-critical)",
  };
  // Chosen per band so an in-segment number always clears contrast on its fill.
  const RISK_INK = { Low: "#ffffff", Medium: "#0b0b0b", High: "#ffffff" };

  S.register({
    id: "roi-by-city",
    page: "financial",
    title: "Return on investment, city by city",
    definition:
      "ROI_Percentage as supplied in the source data, one bar per city, highest first. " +
      "Dubai is labelled because the reference dashboard omitted it entirely.",
    wide: true,
    render: function (container, ctx) {
      const rows = ctx.cities.map((c) => ({
        key: c.city, label: c.city + " · " + c.country, value: c.roi_pct, meta: c,
      }));
      const spec = S.barSpec(rows, { width: 720, labelWidth: 190, alwaysLabel: ["Dubai"] });
      container.appendChild(S.drawBars(spec, {
        ariaLabel: "Return on investment by city, highest first",
        valueFormat: (v) => S.fmt1(v) + "%",
        tickFormat: (v) => S.fmt1(v) + "%",
        colorOf: (mark) => S.regionColorVar(mark.meta.region, ctx.allRegions),
        onSelect: (mark) => ctx.isolate("regions", mark.meta.region),
        tip: (mark) => ({
          value: S.fmt1(mark.value) + "% ROI",
          label: mark.meta.city + ", " + mark.meta.country,
          rows: [
            ["Region", mark.meta.region],
            ["Payback", S.fmt1(mark.meta.payback_years) + " years (" + mark.meta.risk_band + ")"],
            ["Production", S.fmtInt(mark.meta.production_kwh) + " kWh/yr"],
            ["Installations", S.fmtInt(mark.meta.installations)],
          ],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Return on investment by city",
      columns: ["City", "Country", "Region", "ROI %", "Payback (yrs)", "Risk"],
      rows: ctx.cities.map((c) => [
        c.city, c.country, c.region, S.fmt1(c.roi_pct), S.fmt1(c.payback_years), c.risk_band,
      ]),
    }),
  });

  S.register({
    id: "risk-by-region",
    page: "financial",
    title: "Payback risk by region",
    definition:
      "Payback risk: Low under 7 years, Medium 7 to 9 inclusive, High above 9. " +
      "Counts are cities, not weighted by installed capacity.",
    render: function (container, ctx) {
      const rows = ctx.regions.map((r) => ({
        key: r.region, label: r.region, parts: r.risk_counts, meta: r,
      }));
      const spec = S.stackSpec(rows, S.BANDS, {});
      container.appendChild(S.el("ul", { class: "legend" }, S.BANDS.map((band) =>
        S.el("li", null, [
          S.el("span", { class: "swatch", style: "background:" + RISK_COLOR[band] }),
          S.el("span", { text: band }),
        ])
      )));
      container.appendChild(S.drawStack(spec, S.BANDS, {
        ariaLabel: "Cities per payback risk band, by region",
        colorOf: (band) => RISK_COLOR[band],
        inkOn: (band) => RISK_INK[band],
        ariaFor: (mark) => mark.label + ": " + S.BANDS
          .map((b) => S.fmtInt(mark.segments.find((s) => s.key === b).value) + " " + b)
          .join(", "),
        onSelect: (mark) => ctx.isolate("regions", mark.key),
        tip: (mark) => ({
          value: S.fmtInt(mark.total) + " cities",
          label: mark.label,
          rows: mark.segments.map((s) => [s.key + " risk", S.fmtInt(s.value)]),
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Cities per payback risk band",
      columns: ["Region", "Low", "Medium", "High", "Cities"],
      rows: ctx.regions.map((r) => [
        r.region, S.fmtInt(r.risk_counts.Low), S.fmtInt(r.risk_counts.Medium),
        S.fmtInt(r.risk_counts.High), S.fmtInt(r.cities),
      ]),
    }),
  });

  S.register({
    id: "production-by-country",
    page: "production",
    title: "Average annual production by country",
    definition:
      "Mean Avg_Annual_Production_kWh across the cities sampled in each country. " +
      "A country's mean says nothing about how many systems it has installed.",
    wide: true,
    render: function (container, ctx) {
      const rows = ctx.countries
        .slice()
        .sort((a, b) => b.mean_production_kwh - a.mean_production_kwh || a.country.localeCompare(b.country))
        .map((c) => ({ key: c.country, label: c.country, value: c.mean_production_kwh, meta: c }));
      container.appendChild(S.drawBars(S.barSpec(rows, { width: 720, labelWidth: 160 }), {
        ariaLabel: "Mean annual production by country",
        valueFormat: S.fmtInt,
        colorOf: (mark) => S.regionColorVar(mark.meta.region, ctx.allRegions),
        onSelect: (mark) => ctx.isolate("regions", mark.meta.region),
        tip: (mark) => ({
          value: S.fmtInt(mark.value) + " kWh/yr",
          label: mark.label,
          rows: [["Region", mark.meta.region], ["Cities sampled", S.fmtInt(mark.meta.cities)]],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Mean annual production by country",
      columns: ["Country", "Region", "Cities", "Mean kWh/yr"],
      rows: ctx.countries.map((c) => [
        c.country, c.region, S.fmtInt(c.cities), S.fmtInt(c.mean_production_kwh),
      ]),
    }),
  });

  S.register({
    id: "installations-by-region",
    page: "production",
    title: "Installations by region",
    definition:
      "Sum of Solar_Installations_Count. Bars, not an area chart: there is no " +
      "continuity between Africa and Asia for an area to imply.",
    render: function (container, ctx) {
      const rows = ctx.regions
        .slice()
        .sort((a, b) => b.installations - a.installations)
        .map((r) => ({ key: r.region, label: r.region, value: r.installations, meta: r }));
      container.appendChild(S.drawBars(S.barSpec(rows, { width: 560, labelWidth: 120 }), {
        ariaLabel: "Total installations by region",
        valueFormat: S.fmtCompact,
        colorOf: (mark) => S.regionColorVar(mark.key, ctx.allRegions),
        onSelect: (mark) => ctx.isolate("regions", mark.key),
        tip: (mark) => ({
          value: S.fmtInt(mark.value) + " installations",
          label: mark.label,
          rows: [["Cities", S.fmtInt(mark.meta.cities)], ["Mean ROI", S.fmt2(mark.meta.mean_roi) + "%"]],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Installations by region",
      columns: ["Region", "Cities", "Installations"],
      rows: ctx.regions.map((r) => [r.region, S.fmtInt(r.cities), S.fmtInt(r.installations)]),
    }),
  });

  S.register({
    id: "co2-by-country",
    page: "sustainability",
    title: "CO₂ avoided per year by country",
    definition:
      "Sum of CO2_Reduction_Tons_per_Year. This is a fixed multiple of annual " +
      "production, so it ranks countries by output, not by carbon intensity.",
    wide: true,
    render: function (container, ctx) {
      const rows = ctx.countries.map((c) => ({
        key: c.country, label: c.country, value: c.co2_tons, meta: c,
      }));
      container.appendChild(S.drawBars(S.barSpec(rows, { width: 720, labelWidth: 160 }), {
        ariaLabel: "Tonnes of CO2 avoided per year by country",
        valueFormat: (v) => S.fmt2(v) + " t",
        tickFormat: (v) => S.fmt1(v),
        colorOf: (mark) => S.regionColorVar(mark.meta.region, ctx.allRegions),
        onSelect: (mark) => ctx.isolate("regions", mark.meta.region),
        tip: (mark) => ({
          value: S.fmt2(mark.value) + " t CO₂/yr",
          label: mark.label,
          rows: [["Region", mark.meta.region], ["Cities", S.fmtInt(mark.meta.cities)]],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "CO₂ avoided per year by country",
      columns: ["Country", "Region", "Cities", "Tonnes CO₂/yr"],
      rows: ctx.countries.map((c) => [
        c.country, c.region, S.fmtInt(c.cities), S.fmt2(c.co2_tons),
      ]),
    }),
  });
})(globalThis.SOLAR);
