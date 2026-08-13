/* charts_map.js — equirectangular city map, bubbles sized by installations.
   No basemap: a coastline is decoration that cannot be fetched anyway. The
   graticule and the named tropics carry the geography instead. */
(function (S) {
  "use strict";

  const R_MIN = 3;
  const R_MAX = 26;
  const GUIDES = [
    { lat: 23.44, label: "Tropic of Cancer" },
    { lat: 0, label: "Equator" },
    { lat: -23.44, label: "Tropic of Capricorn" },
  ];

  S.project = function (lat, lon, width, height) {
    return {
      x: ((lon + 180) / 360) * width,
      y: ((90 - lat) / 180) * height,
    };
  };

  S.bubbleRadius = function (value, maxValue, rMin, rMax) {
    if (!(maxValue > 0)) return rMin;
    return rMin + (rMax - rMin) * Math.sqrt(Math.max(0, value) / maxValue);
  };

  S.mapSpec = function (cities, options) {
    const o = Object.assign({ width: 720, height: 360, rMin: R_MIN, rMax: R_MAX }, options || {});
    const maxInstallations = cities.length
      ? Math.max.apply(null, cities.map((c) => c.installations))
      : 0;

    const marks = cities.map(function (city) {
      const point = S.project(city.lat, city.lon, o.width, o.height);
      return {
        key: city.city,
        label: city.city + ", " + city.country,
        cx: point.x,
        cy: point.y,
        r: S.bubbleRadius(city.installations, maxInstallations, o.rMin, o.rMax),
        meta: city,
      };
    });
    // Largest first: a small bubble drawn under a large one is unreachable.
    marks.sort((a, b) => b.r - a.r || a.key.localeCompare(b.key));

    const meridians = [];
    for (let lon = -180; lon <= 180; lon += 30) {
      meridians.push({ lon: lon, x: S.project(0, lon, o.width, o.height).x });
    }
    const parallels = [];
    for (let lat = -90; lat <= 90; lat += 30) {
      parallels.push({ lat: lat, y: S.project(lat, 0, o.width, o.height).y });
    }

    return {
      marks: marks,
      graticule: { meridians: meridians, parallels: parallels },
      guides: GUIDES.map((g) => ({
        label: g.label, lat: g.lat, y: S.project(g.lat, 0, o.width, o.height).y,
      })),
      width: o.width,
      height: o.height,
      maxInstallations: maxInstallations,
      padTop: 0,
      padBottom: 0,
      plotLeft: 0,
      plotRight: o.width,
      ticks: [],
    };
  };

  S.drawMap = function (spec, options) {
    const o = options || {};
    const svg = S.svgRoot(spec, o.ariaLabel || "World map of solar installations");

    const grid = S.svgEl("g", { class: "graticule" });
    for (const meridian of spec.graticule.meridians) {
      grid.appendChild(S.svgEl("line", {
        class: "gridline", x1: meridian.x, x2: meridian.x, y1: 0, y2: spec.height,
      }));
    }
    for (const parallel of spec.graticule.parallels) {
      grid.appendChild(S.svgEl("line", {
        class: "gridline", x1: 0, x2: spec.width, y1: parallel.y, y2: parallel.y,
      }));
    }
    svg.appendChild(grid);

    for (const guide of spec.guides) {
      svg.appendChild(S.svgEl("line", {
        class: "axis-line", x1: 0, x2: spec.width, y1: guide.y, y2: guide.y,
      }));
      svg.appendChild(S.svgEl("text", {
        class: "note", x: 6, y: guide.y - 5, text: guide.label,
      }));
    }

    for (const mark of spec.marks) {
      const group = S.svgEl("g", { class: "mark", "data-key": mark.key });
      group.appendChild(S.svgEl("circle", {
        cx: mark.cx, cy: mark.cy, r: mark.r,
        fill: "var(--series-1)", "fill-opacity": "0.32",
      }));
      group.appendChild(S.svgEl("circle", {
        cx: mark.cx, cy: mark.cy, r: 2.5, fill: "var(--series-1)",
      }));
      const hit = S.svgEl("circle", {
        class: "hit",
        cx: mark.cx, cy: mark.cy, r: Math.max(12, mark.r),
        tabindex: "0",
        "aria-label": mark.label + ": " + S.fmtInt(mark.meta.installations) + " installations",
      });
      S.attachTip(hit, () => o.tip(mark));
      if (o.onSelect) hit.addEventListener("click", () => o.onSelect(mark));
      group.appendChild(hit);
      svg.appendChild(group);
    }
    return svg;
  };

  S.register({
    id: "world-map",
    page: "sustainability",
    title: "Where the 48 cities are",
    definition:
      "Equirectangular projection of Latitude and Longitude. Bubble area — not " +
      "radius — is proportional to Solar_Installations_Count. No basemap: the " +
      "graticule and tropics carry the geography.",
    wide: true,
    render: function (container, ctx) {
      const spec = S.mapSpec(ctx.cities, { width: 720, height: 360 });
      container.appendChild(S.drawMap(spec, {
        ariaLabel: "World map, bubble area proportional to installations",
        onSelect: (mark) => ctx.isolate("regions", mark.meta.region),
        tip: (mark) => ({
          value: S.fmtInt(mark.meta.installations) + " installations",
          label: mark.label,
          rows: [
            ["Region", mark.meta.region],
            ["ROI", S.fmt1(mark.meta.roi_pct) + "%"],
            ["CO₂ avoided", S.fmt2(mark.meta.co2_tons) + " t/yr"],
          ],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Cities by location and installed count",
      columns: ["City", "Country", "Latitude", "Longitude", "Installations"],
      rows: ctx.cities.map((c) => [
        c.city, c.country, S.fmt2(c.lat), S.fmt2(c.lon), S.fmtInt(c.installations),
      ]),
    }),
  });
})(globalThis.SOLAR);
