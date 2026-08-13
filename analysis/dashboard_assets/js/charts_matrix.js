/* charts_matrix.js — region → country → city, expandable.
   Every number goes through the en-US formatters: the reference dashboard
   printed 26.64 as "26 64", which is what a locale-dependent separator does. */
(function (S) {
  "use strict";

  S.MATRIX_COLUMNS = ["Region · country · city", "Cities", "CO₂ t/yr", "Installations", "kWh/yr"];

  S.matrixRows = function (regions, countries, cities) {
    const citiesByCountry = S.groupBy(cities, (c) => c.country);
    const rows = [];

    for (const region of regions) {
      const regionKey = "region:" + region.region;
      rows.push({
        level: 0,
        key: regionKey,
        parent: null,
        label: region.region,
        region: region.region,
        hasChildren: true,
        cells: [
          S.fmtInt(region.cities),
          S.fmt2(region.co2_tons),
          S.fmtInt(region.installations),
          S.fmtInt(region.production_kwh),
        ],
      });

      const inRegion = countries.filter((c) => c.region === region.region);
      for (const country of inRegion) {
        const countryKey = "country:" + country.country;
        const own = citiesByCountry.get(country.country) || [];
        rows.push({
          level: 1,
          key: countryKey,
          parent: regionKey,
          label: country.country,
          region: region.region,
          hasChildren: own.length > 0,
          cells: [
            S.fmtInt(country.cities),
            S.fmt2(country.co2_tons),
            S.fmtInt(country.installations),
            S.fmtInt(own.reduce((sum, c) => sum + c.production_kwh, 0)),
          ],
        });

        for (const city of own) {
          rows.push({
            level: 2,
            key: "city:" + city.city,
            parent: countryKey,
            label: city.city,
            region: region.region,
            hasChildren: false,
            cells: [
              "1",
              S.fmt2(city.co2_tons),
              S.fmtInt(city.installations),
              S.fmtInt(city.production_kwh),
            ],
          });
        }
      }
    }
    return rows;
  };

  S.drawMatrix = function (rows, options) {
    const o = options || {};
    const expanded = new Set();
    const elements = new Map();
    const byKey = new Map(rows.map((r) => [r.key, r]));

    function visible(row) {
      let parent = row.parent;
      while (parent) {
        if (!expanded.has(parent)) return false;
        const parentRow = byKey.get(parent);
        parent = parentRow ? parentRow.parent : null;
      }
      return true;
    }

    function refresh() {
      for (const row of rows) {
        const tr = elements.get(row.key);
        tr.hidden = !visible(row);
        const button = tr.querySelector("button");
        if (button) button.setAttribute("aria-expanded", String(expanded.has(row.key)));
      }
    }

    const body = S.el("tbody");
    for (const row of rows) {
      const first = S.el("th", { scope: "row" });

      if (row.hasChildren) {
        const twist = S.el("button", {
          type: "button", class: "twist",
          "aria-expanded": "false",
          "aria-label": "Expand " + row.label,
          text: "▸",
        });
        twist.addEventListener("click", function () {
          if (expanded.has(row.key)) expanded.delete(row.key);
          else expanded.add(row.key);
          twist.textContent = expanded.has(row.key) ? "▾" : "▸";
          refresh();
        });
        first.appendChild(twist);
      }

      if (row.level === 0 && o.colorOf) {
        first.appendChild(S.el("span", {
          class: "region-key", style: "background:" + o.colorOf(row.region),
        }));
      }
      first.appendChild(S.el("span", { text: row.label }));

      const tr = S.el("tr", { "data-level": String(row.level), "data-key": row.key },
        [first].concat(row.cells.map((cell) => S.el("td", { text: cell }))));
      elements.set(row.key, tr);
      body.appendChild(tr);
    }

    const table = S.el("table", { class: "matrix" }, [
      S.el("caption", { text: o.caption || "Region, country and city detail" }),
      S.el("thead", null, [
        S.el("tr", null, S.MATRIX_COLUMNS.map((c) => S.el("th", { scope: "col", text: c }))),
      ]),
      body,
    ]);
    refresh();
    return table;
  };

  S.register({
    id: "region-country-city",
    page: "sustainability",
    title: "Region, country and city detail",
    definition:
      "Every figure rolled up three ways from the same 48 rows. Expand a region " +
      "to see its countries, a country to see its cities. Totals reconcile exactly.",
    wide: true,
    render: function (container, ctx) {
      container.appendChild(S.drawMatrix(
        S.matrixRows(ctx.regions, ctx.countries, ctx.cities),
        {
          caption: "Region, country and city detail — " + ctx.cities.length + " cities in view",
          colorOf: (region) => S.regionColorVar(region, ctx.allRegions),
        }
      ));
    },
  });
})(globalThis.SOLAR);
