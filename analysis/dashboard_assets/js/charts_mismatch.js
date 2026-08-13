/* charts_mismatch.js — the page's thesis, drawn.
   Twelve largest deployments on the left, twelve best returns on the right, a
   connector only where a city is in both. The gap is the point. */
(function (S) {
  "use strict";

  const DEFAULTS = { width: 700, count: 12, padTop: 40, padBottom: 16, rowHeight: 22, columnWidth: 210 };

  function column(cities, valueOf, count, x, o) {
    return cities
      .slice()
      .sort((a, b) => valueOf(b) - valueOf(a) || a.city.localeCompare(b.city))
      .slice(0, count)
      .map(function (city, i) {
        return {
          key: city.city,
          label: city.city,
          value: valueOf(city),
          rank: i + 1,
          meta: city,
          x: x,
          y: o.padTop + i * o.rowHeight,
          w: o.columnWidth,
          h: o.rowHeight,
        };
      });
  }

  S.mismatchSpec = function (cities, options) {
    const o = Object.assign({}, DEFAULTS, options || {});
    const count = Math.min(o.count, cities.length);
    const left = column(cities, (c) => c.installations, count, 0, o);
    const right = column(cities, (c) => c.roi_pct, count, o.width - o.columnWidth, o);

    const rightByKey = new Map(right.map((r) => [r.key, r]));
    const gapLeft = o.columnWidth;
    const gapRight = o.width - o.columnWidth;

    const links = [];
    for (const row of left) {
      const match = rightByKey.get(row.key);
      if (!match) continue;
      const y1 = row.y + row.h / 2;
      const y2 = match.y + match.h / 2;
      const midpoint = (gapLeft + gapRight) / 2;
      links.push({
        key: row.key,
        y1: y1,
        y2: y2,
        d: "M" + gapLeft + "," + y1 +
           " C" + midpoint + "," + y1 + " " + midpoint + "," + y2 + " " + gapRight + "," + y2,
      });
    }

    return {
      left: left,
      right: right,
      links: links,
      width: o.width,
      height: o.padTop + Math.max(count, 1) * o.rowHeight + o.padBottom,
      columnWidth: o.columnWidth,
      padTop: o.padTop,
      padBottom: o.padBottom,
      plotLeft: 0,
      plotRight: o.width,
      ticks: [],
    };
  };

  function columnGroup(rows, spec, o, anchor, format, heading) {
    const group = S.svgEl("g", { class: "rank-column" });
    const headingX = anchor === "end" ? spec.width : 0;
    group.appendChild(S.svgEl("text", {
      class: "facet-title", x: headingX, y: 20, "text-anchor": anchor, text: heading,
    }));
    for (const row of rows) {
      group.appendChild(S.svgEl("circle", {
        cx: anchor === "end" ? row.x + row.w : row.x,
        cy: row.y + row.h / 2,
        r: 4,
        fill: o.colorOf(row),
      }));
      group.appendChild(S.svgEl("text", {
        class: "cat-label",
        x: anchor === "end" ? row.x + row.w - 12 : row.x + 12,
        y: row.y + row.h / 2 + 4,
        "text-anchor": anchor,
        text: row.rank + ". " + row.label + " · " + format(row.value),
      }));
    }
    return group;
  }

  S.drawMismatch = function (spec, options) {
    const o = options || {};
    const svg = S.svgRoot(spec, "The twelve largest solar deployments against the twelve best returns");

    const linkGroup = S.svgEl("g", { class: "links" });
    for (const link of spec.links) {
      linkGroup.appendChild(S.svgEl("path", {
        d: link.d, fill: "none", stroke: "var(--text-muted)", "stroke-width": 2,
      }));
    }
    svg.appendChild(linkGroup);

    svg.appendChild(columnGroup(spec.left, spec, o, "start", S.fmtCompact, "Most installations"));
    svg.appendChild(columnGroup(spec.right, spec, o, "end", (v) => S.fmt1(v) + "%", "Best return"));
    return svg;
  };

  S.register({
    id: "mismatch",
    page: "financial",
    title: "The mismatch",
    definition:
      "Left: the cities with the most installations. Right: the cities with the " +
      "highest ROI. A line is drawn only where a city appears in both columns.",
    wide: true,
    render: function (container, ctx) {
      const spec = S.mismatchSpec(ctx.cities, { width: 700, count: 12 });
      const overlap = spec.links.length;
      container.appendChild(S.el("div", { class: "hero" }, [
        S.el("p", { class: "hero-figure", text: String(ctx.payload.correlations.installations_vs_roi) }),
        S.el("p", { class: "hero-label",
          text: "correlation between where solar is installed and where it pays back. " +
                overlap + " of " + spec.left.length + " cities appear in both rankings." }),
      ]));
      container.appendChild(S.drawMismatch(spec, {
        colorOf: (row) => S.regionColorVar(row.meta.region, ctx.allRegions),
      }));
    },
    callout: (ctx) =>
      "Installed capacity is concentrated in China, India and Europe. Return is " +
      "concentrated in Phoenix, Dubai and Cairo. At r = " +
      ctx.payload.correlations.installations_vs_roi +
      ", knowing where panels went tells you almost nothing about where they pay back.",
    table: (ctx) => ({
      caption: "Deployment rank against return rank",
      columns: ["City", "Installations", "ROI %"],
      rows: ctx.cities
        .slice()
        .sort((a, b) => b.installations - a.installations)
        .slice(0, 12)
        .map((c) => [c.city, S.fmtInt(c.installations), S.fmt1(c.roi_pct)]),
    }),
  });
})(globalThis.SOLAR);
