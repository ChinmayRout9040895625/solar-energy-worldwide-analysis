/* rollup.js — region/country/total rollups, mirroring analysis/aggregate.py.
   A payback-risk filter changes a region's membership, so these totals cannot
   be read off the payload; they are recomputed from the filtered city list.
   tests/js/rollup.test.mjs asserts this agrees with the Python output. */
(function (S) {
  "use strict";

  const MIN_CITIES_FOR_CONSISTENCY = 3;
  const SMALL_SAMPLE_MAX = 5;
  const BANDS = ["Low", "Medium", "High"];

  S.round2 = (v) => Math.round((v + Number.EPSILON) * 100) / 100;

  S.groupBy = function (rows, keyFn) {
    const groups = new Map();
    for (const row of rows) {
      const key = keyFn(row);
      const bucket = groups.get(key);
      if (bucket) bucket.push(row);
      else groups.set(key, [row]);
    }
    return groups;
  };

  const sum = (rows, accessor) => rows.reduce((acc, row) => acc + accessor(row), 0);
  const mean = (rows, accessor) => (rows.length ? sum(rows, accessor) / rows.length : 0);

  S.consistencyOf = function (values) {
    if (values.length < MIN_CITIES_FOR_CONSISTENCY) return null;
    const mu = values.reduce((a, b) => a + b, 0) / values.length;
    if (mu === 0) return null;
    const variance =
      values.reduce((acc, v) => acc + (v - mu) * (v - mu), 0) / (values.length - 1);
    const cv = Math.sqrt(variance) / mu;
    return Math.max(0, Math.min(1, 1 - cv));
  };

  S.denseRankDesc = function (entries) {
    const distinct = Array.from(new Set(entries.map(([, v]) => v))).sort((a, b) => b - a);
    const rankOf = new Map(distinct.map((v, i) => [v, i + 1]));
    return new Map(entries.map(([name, v]) => [name, rankOf.get(v)]));
  };

  S.riskCountsOf = function (cities) {
    const counts = { Low: 0, Medium: 0, High: 0 };
    for (const city of cities) {
      if (BANDS.indexOf(city.risk_band) >= 0) counts[city.risk_band] += 1;
    }
    return counts;
  };

  S.totalsOf = function (cities) {
    return {
      cities: cities.length,
      countries: new Set(cities.map((c) => c.country)).size,
      regions: new Set(cities.map((c) => c.region)).size,
      co2_tons: S.round2(sum(cities, (c) => c.co2_tons)),
      installations: sum(cities, (c) => c.installations),
      production_kwh: sum(cities, (c) => c.production_kwh),
    };
  };

  S.regionRollup = function (cities) {
    const groups = S.groupBy(cities, (c) => c.region);
    const means = Array.from(groups, ([region, rows]) => [region, mean(rows, (c) => c.roi_pct)]);
    const ranks = S.denseRankDesc(means);

    const records = Array.from(groups, function ([region, rows]) {
      const consistency = S.consistencyOf(rows.map((c) => c.production_kwh));
      return {
        region: region,
        cities: rows.length,
        rank: ranks.get(region),
        mean_roi: S.round2(mean(rows, (c) => c.roi_pct)),
        co2_tons: S.round2(sum(rows, (c) => c.co2_tons)),
        installations: sum(rows, (c) => c.installations),
        production_kwh: sum(rows, (c) => c.production_kwh),
        consistency: consistency === null ? null : S.round2(consistency),
        small_sample: rows.length < SMALL_SAMPLE_MAX,
        risk_counts: S.riskCountsOf(rows),
      };
    });

    records.sort((a, b) => a.rank - b.rank || a.region.localeCompare(b.region));
    return records;
  };

  S.countryRollup = function (cities) {
    const groups = S.groupBy(cities, (c) => c.country);
    const records = Array.from(groups, ([country, rows]) => ({
      country: country,
      region: rows[0].region,
      cities: rows.length,
      mean_roi: S.round2(mean(rows, (c) => c.roi_pct)),
      mean_production_kwh: S.round2(mean(rows, (c) => c.production_kwh)),
      co2_tons: S.round2(sum(rows, (c) => c.co2_tons)),
      installations: sum(rows, (c) => c.installations),
      _co2: sum(rows, (c) => c.co2_tons),
    }));

    // Sort on the unrounded total, exactly as country_records does.
    records.sort((a, b) => b._co2 - a._co2 || a.country.localeCompare(b.country));
    for (const record of records) delete record._co2;
    return records;
  };
})(globalThis.SOLAR);
