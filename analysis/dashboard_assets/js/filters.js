/* filters.js — pure filter state. No DOM, no side effects. */
(function (S) {
  "use strict";

  S.BANDS = ["Low", "Medium", "High"];

  S.PAGES = [
    { id: "financial", tabId: "tab-financial", label: "Financial performance" },
    { id: "production", tabId: "tab-production", label: "Production" },
    { id: "sustainability", tabId: "tab-sustainability", label: "Sustainability" },
  ];

  S.allRegionsOf = (payload) =>
    Array.from(new Set(payload.cities.map((c) => c.region))).sort();

  S.initialState = function (payload) {
    return {
      regions: S.allRegionsOf(payload),
      bands: S.BANDS.slice(),
      page: "financial",
    };
  };

  const order = (values, all) => all.filter((v) => values.indexOf(v) >= 0);

  S.toggleValue = function (selected, value, all) {
    const next = selected.indexOf(value) >= 0
      ? selected.filter((v) => v !== value)
      : selected.concat([value]);
    // An empty selection would render an empty dashboard, which reads as a bug
    // rather than a choice. Clearing the last chip means "show everything".
    return next.length ? order(next, all) : all.slice();
  };

  S.isolateValue = function (selected, value, all) {
    const isolated = selected.length === 1 && selected[0] === value;
    return isolated ? all.slice() : [value];
  };

  S.filterCities = function (cities, state) {
    return cities.filter(
      (c) => state.regions.indexOf(c.region) >= 0 && state.bands.indexOf(c.risk_band) >= 0
    );
  };

  S.describeFilter = function (cities, filtered, state, allRegions, allBands) {
    const parts = [filtered.length + " of " + cities.length + " cities"];
    parts.push(
      state.regions.length === allRegions.length
        ? "all regions"
        : state.regions.join(", ")
    );
    parts.push(
      state.bands.length === allBands.length
        ? "all payback risk bands"
        : state.bands.join(", ") + " payback risk"
    );
    return parts.join(" · ");
  };
})(globalThis.SOLAR);
