/* charts_scatter.js — clouds and small multiples.
   Region colour is deliberately absent from the single-panel clouds: seven hues
   in one all-pairs form is past what the validated palette supports, so the
   regional view is faceted instead. */
(function (S) {
  "use strict";

  const SCATTER_DEFAULTS = {
    width: 520, height: 320, padTop: 20, padRight: 20, padBottom: 40, padLeft: 60,
    radius: 5, xTickCount: 5, yTickCount: 4,
  };

  function padded(lo, hi) {
    const pad = (hi - lo) * 0.08 || Math.max(Math.abs(hi) * 0.1, 1);
    return [lo - pad, hi + pad];
  }

  S.scatterSpec = function (points, options) {
    const o = Object.assign({}, SCATTER_DEFAULTS, options || {});
    const plotLeft = o.padLeft;
    const plotRight = o.width - o.padRight;
    const plotTop = o.padTop;
    const plotBottom = o.height - o.padBottom;

    const xDomain = o.xDomain || padded.apply(null, S.extent(points, (p) => p.x));
    const yDomain = o.yDomain || padded.apply(null, S.extent(points, (p) => p.y));
    const x = S.linear(xDomain[0], xDomain[1], plotLeft, plotRight);
    const y = S.linear(yDomain[0], yDomain[1], plotBottom, plotTop);

    const xTicks = S.ticks(xDomain[0], xDomain[1], o.xTickCount).map((v) => ({ value: v, x: x(v) }));

    return {
      marks: points.map((p) => ({
        key: p.key, label: p.label, meta: p.meta,
        value: { x: p.x, y: p.y },
        cx: x(p.x), cy: y(p.y), r: o.radius,
      })),
      xTicks: xTicks,
      yTicks: S.ticks(yDomain[0], yDomain[1], o.yTickCount).map((v) => ({ value: v, y: y(v) })),
      width: o.width, height: o.height,
      padTop: o.padTop, padBottom: o.padBottom,
      plotLeft: plotLeft, plotRight: plotRight, plotTop: plotTop, plotBottom: plotBottom,
      // drawAxisX reads `ticks`; the x ticks are the same list.
      ticks: xTicks,
      xDomain: xDomain, yDomain: yDomain,
    };
  };

  // Nearest-point lookup: the pointer only has to be closest, never dead-centre.
  S.nearestMark = function (spec, px, py) {
    let best = null;
    let bestDistance = Infinity;
    for (const mark of spec.marks) {
      const dx = mark.cx - px;
      const dy = mark.cy - py;
      const distance = dx * dx + dy * dy;
      if (distance < bestDistance) { bestDistance = distance; best = mark; }
    }
    return best;
  };

  S.facetSpecs = function (points, options) {
    const o = Object.assign({ columns: 4, gap: 20, panelHeight: 150, width: 720 }, options);
    const groups = S.groupBy(points, o.facetOf);
    const keys = o.order ? o.order.filter((k) => groups.has(k)) : Array.from(groups.keys()).sort();
    const panelWidth = (o.width - o.gap * (o.columns - 1)) / o.columns;

    const xDomain = o.xDomain || padded.apply(null, S.extent(points, (p) => p.x));
    const yDomain = o.yDomain || padded.apply(null, S.extent(points, (p) => p.y));

    const panelOptions = {
      width: panelWidth, height: o.panelHeight,
      padTop: 22, padRight: 8, padBottom: 26, padLeft: 40,
      radius: 4, xTickCount: 3, yTickCount: 3,
      xDomain: xDomain, yDomain: yDomain,
    };
    const contextSpec = S.scatterSpec(points, panelOptions);

    return keys.map(function (key, i) {
      const col = i % o.columns;
      const row = Math.floor(i / o.columns);
      const spec = S.scatterSpec(groups.get(key), panelOptions);
      return {
        key: key,
        spec: spec,
        marks: spec.marks,
        contextMarks: contextSpec.marks,
        col: col,
        row: row,
        x: col * (panelWidth + o.gap),
        y: row * (o.panelHeight + o.gap),
      };
    });
  };

  S.drawScatter = function (spec, options) {
    const o = options || {};
    const svg = S.svgRoot(spec, o.ariaLabel || "Scatter plot");
    svg.appendChild(S.drawAxisY(spec, o.yFormat || S.fmtCompact));
    svg.appendChild(S.drawAxisX(spec, o.xFormat || S.fmtCompact));
    svg.appendChild(S.axisTitle(o.xTitle, (spec.plotLeft + spec.plotRight) / 2, spec.height - 4));
    svg.appendChild(S.axisTitle(o.yTitle, 14, (spec.plotTop + spec.plotBottom) / 2, "middle", true));

    const cloud = S.svgEl("g", { class: "cloud" });
    for (const mark of spec.marks) {
      cloud.appendChild(S.svgEl("circle", {
        cx: mark.cx, cy: mark.cy, r: mark.r + 2, fill: "var(--surface-1)",
      }));
      cloud.appendChild(S.svgEl("circle", {
        class: "mark", "data-key": mark.key,
        cx: mark.cx, cy: mark.cy, r: mark.r,
        fill: o.colorOf ? o.colorOf(mark) : "var(--series-1)",
      }));
    }
    svg.appendChild(cloud);

    for (const mark of spec.marks.filter((m) => (o.labelled || []).indexOf(m.key) >= 0)) {
      svg.appendChild(S.svgEl("text", {
        class: "value-label",
        x: mark.cx + mark.r + 6, y: mark.cy + 4, text: mark.label,
      }));
    }

    // One transparent surface carries hover for the whole cloud; the nearest
    // point wins, so an 8px dot never has to be hit dead-centre.
    const surface = S.svgEl("rect", {
      class: "hit",
      x: spec.plotLeft, y: spec.plotTop,
      width: spec.plotRight - spec.plotLeft,
      height: spec.plotBottom - spec.plotTop,
    });
    surface.addEventListener("pointermove", function (event) {
      const mark = S.nearestMark(spec, event.offsetX, event.offsetY);
      if (mark) { S.showTip(o.tip(mark)); S.moveTip(event); }
    });
    surface.addEventListener("pointerleave", () => S.hideTip());
    svg.appendChild(surface);
    return svg;
  };

  S.drawFacets = function (facets, options) {
    const o = options || {};
    const last = facets[facets.length - 1];
    const outer = {
      width: o.width,
      height: last ? last.y + last.spec.height : 1,
      plotLeft: 0, plotRight: o.width,
      padTop: 0, padBottom: 0, ticks: [],
    };
    const svg = S.svgRoot(outer, o.ariaLabel || "Small multiples");

    for (const facet of facets) {
      const group = S.svgEl("g", {
        class: "facet", "data-key": facet.key,
        transform: "translate(" + facet.x + "," + facet.y + ")",
      });
      group.appendChild(S.svgEl("text", {
        class: "facet-title", x: facet.spec.plotLeft, y: 12,
        text: facet.key + " · " + facet.marks.length,
      }));
      group.appendChild(S.drawAxisY(facet.spec, o.yFormat || S.fmtCompact));
      group.appendChild(S.drawAxisX(facet.spec, o.xFormat || S.fmt1));

      for (const mark of facet.contextMarks) {
        group.appendChild(S.svgEl("circle", {
          class: "context-dot", cx: mark.cx, cy: mark.cy, r: 2,
        }));
      }
      for (const mark of facet.marks) {
        group.appendChild(S.svgEl("circle", {
          cx: mark.cx, cy: mark.cy, r: mark.r + 2, fill: "var(--surface-1)",
        }));
        group.appendChild(S.svgEl("circle", {
          class: "mark", "data-key": mark.key,
          cx: mark.cx, cy: mark.cy, r: mark.r, fill: o.colorOf(facet.key),
        }));
      }

      const surface = S.svgEl("rect", {
        class: "hit",
        x: facet.spec.plotLeft, y: facet.spec.plotTop,
        width: facet.spec.plotRight - facet.spec.plotLeft,
        height: facet.spec.plotBottom - facet.spec.plotTop,
        tabindex: "0",
        "aria-label": facet.key + ": " + facet.marks.length + " cities",
      });
      surface.addEventListener("pointermove", function (event) {
        const mark = S.nearestMark(facet.spec, event.offsetX - facet.x, event.offsetY - facet.y);
        if (mark) { S.showTip(o.tip(mark)); S.moveTip(event); }
      });
      surface.addEventListener("pointerleave", () => S.hideTip());
      if (o.onSelect) surface.addEventListener("click", () => o.onSelect(facet.key));
      group.appendChild(surface);
      svg.appendChild(group);
    }
    return svg;
  };

  S.register({
    id: "installations-vs-roi",
    page: "financial",
    title: "Where solar is installed against where it pays back",
    definition:
      "Solar_Installations_Count on a square-root axis against ROI_Percentage. " +
      "One dot per city; the correlation is quoted from the build, not refitted here.",
    wide: true,
    render: function (container, ctx) {
      const points = ctx.cities.map((c) => ({
        key: c.city, label: c.city, x: Math.sqrt(c.installations), y: c.roi_pct, meta: c,
      }));
      const spec = S.scatterSpec(points, { width: 700, height: 340, padLeft: 64 });
      container.appendChild(S.drawScatter(spec, {
        ariaLabel: "Installations against return on investment, one dot per city",
        xTitle: "Installations (square-root scale)",
        yTitle: "ROI %",
        xFormat: (v) => S.fmtCompact(Math.round(v * v)),
        yFormat: (v) => S.fmt1(v) + "%",
        labelled: ["Phoenix", "Dubai", "Cairo"],
        tip: (mark) => ({
          value: S.fmt1(mark.meta.roi_pct) + "% ROI",
          label: mark.meta.city + ", " + mark.meta.country,
          rows: [
            ["Installations", S.fmtInt(mark.meta.installations)],
            ["Region", mark.meta.region],
          ],
        }),
      }));
    },
    callout: (ctx) =>
      "Correlation between installations and ROI is " +
      ctx.payload.correlations.installations_vs_roi +
      " — close to nothing. The largest deployments are in China, India and Europe; " +
      "the best returns are in Phoenix, Dubai and Cairo. Installed capacity is not " +
      "following the return.",
    table: (ctx) => ({
      caption: "Installations against ROI",
      columns: ["City", "Region", "Installations", "ROI %"],
      rows: ctx.cities.map((c) => [c.city, c.region, S.fmtInt(c.installations), S.fmt1(c.roi_pct)]),
    }),
  });

  S.register({
    id: "ghi-vs-production",
    page: "production",
    title: "Irradiance against production, region by region",
    definition:
      "GHI_kWh_per_m2 against Avg_Annual_Production_kWh, one panel per region on " +
      "shared axes. Grey dots are all cities in view, for context; coloured dots are the panel's region.",
    wide: true,
    render: function (container, ctx) {
      const points = ctx.cities.map((c) => ({
        key: c.city, label: c.city, x: c.ghi, y: c.production_kwh, meta: c,
      }));
      const facets = S.facetSpecs(points, {
        facetOf: (p) => p.meta.region,
        order: ctx.allRegions,
        width: 700, columns: 4, panelHeight: 160, gap: 18,
      });
      container.appendChild(S.drawFacets(facets, {
        width: 700, columns: 4,
        ariaLabel: "Irradiance against annual production, one panel per region",
        xFormat: S.fmt1,
        yFormat: S.fmtCompact,
        colorOf: (region) => S.regionColorVar(region, ctx.allRegions),
        onSelect: (region) => ctx.isolate("regions", region),
        tip: (mark) => ({
          value: S.fmtInt(mark.meta.production_kwh) + " kWh/yr",
          label: mark.meta.city + ", " + mark.meta.country,
          rows: [
            ["GHI", S.fmt1(mark.meta.ghi) + " kWh/m²"],
            ["Sunlight", S.fmtInt(mark.meta.sunlight_hours) + " hrs/yr"],
          ],
        }),
      }));
    },
    callout: (ctx) =>
      "Irradiance and production correlate at " + ctx.payload.correlations.ghi_vs_production +
      ". This is the one relationship in the dataset that is physical rather than " +
      "arithmetic — the rest of the money columns are rescalings of production.",
    table: (ctx) => ({
      caption: "Irradiance and production by city",
      columns: ["City", "Region", "GHI kWh/m²", "kWh/yr"],
      rows: ctx.cities.map((c) => [c.city, c.region, S.fmt1(c.ghi), S.fmtInt(c.production_kwh)]),
    }),
  });

  S.register({
    id: "roi-vs-viability",
    page: "sustainability",
    title: "ROI against the supplied viability score",
    definition:
      "ROI_Percentage against Solar_Viability_Score. Kept because the near-perfect " +
      "fit is itself the finding: the score adds no information ROI does not already carry.",
    render: function (container, ctx) {
      const points = ctx.cities.map((c) => ({
        key: c.city, label: c.city, x: c.viability, y: c.roi_pct, meta: c,
      }));
      container.appendChild(S.drawScatter(S.scatterSpec(points, { width: 520, height: 320 }), {
        ariaLabel: "Viability score against return on investment",
        xTitle: "Solar viability score",
        yTitle: "ROI %",
        xFormat: S.fmtInt,
        yFormat: (v) => S.fmt1(v) + "%",
        labelled: ["Phoenix"],
        tip: (mark) => ({
          value: S.fmt1(mark.meta.roi_pct) + "% ROI",
          label: mark.meta.city,
          rows: [["Viability score", S.fmtInt(mark.meta.viability)]],
        }),
      }));
    },
    callout: (ctx) =>
      "These two columns correlate at " + ctx.payload.correlations.roi_vs_viability +
      ". Treat the viability score as a restatement of ROI, not as a second opinion.",
    table: (ctx) => ({
      caption: "Viability score against ROI",
      columns: ["City", "Viability", "ROI %"],
      rows: ctx.cities.map((c) => [c.city, S.fmtInt(c.viability), S.fmt1(c.roi_pct)]),
    }),
  });
})(globalThis.SOLAR);
