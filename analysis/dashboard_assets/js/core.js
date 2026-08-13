/* core.js — formatting, scales, ticks, and the region colour contract. */
(function (S) {
  "use strict";

  const NF0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const NF1 = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 1, maximumFractionDigits: 1,
  });
  const NF2 = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });

  S.fmtInt = (n) => NF0.format(n);
  S.fmt1 = (n) => NF1.format(n);
  S.fmt2 = (n) => NF2.format(n);

  S.fmtCompact = function (n) {
    const abs = Math.abs(n);
    if (abs >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (abs >= 1e5) return Math.round(n / 1e3) + "K";
    return NF0.format(n);
  };

  S.linear = function (d0, d1, r0, r1) {
    const span = d1 - d0;
    const slope = span === 0 ? 0 : (r1 - r0) / span;
    return (v) => r0 + (v - d0) * slope;
  };

  S.niceStep = function (raw) {
    if (!(raw > 0)) return 1;
    const magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
    const norm = raw / magnitude;
    const step = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
    return step * magnitude;
  };

  S.ticks = function (min, max, count) {
    if (!(max > min)) return [min];
    const step = S.niceStep((max - min) / Math.max(1, count));
    const decimals = Math.max(0, -Math.floor(Math.log10(step)) + 1);
    const out = [];
    for (let i = Math.ceil(min / step); i * step <= max + step * 1e-9; i += 1) {
      out.push(Number((i * step).toFixed(decimals)));
    }
    return out;
  };

  S.extent = function (rows, accessor) {
    if (!rows.length) return [0, 0];
    let lo = Infinity;
    let hi = -Infinity;
    for (const row of rows) {
      const v = accessor(row);
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    return [lo, hi];
  };

  S.roundedBarPath = function (x, y, w, h, r) {
    const radius = Math.max(0, Math.min(r, w, h / 2));
    const end = x + w;
    return [
      "M" + x + "," + y,
      "H" + (end - radius),
      "A" + radius + "," + radius + " 0 0 1 " + end + "," + (y + radius),
      "V" + (y + h - radius),
      "A" + radius + "," + radius + " 0 0 1 " + (end - radius) + "," + (y + h),
      "H" + x,
      "Z",
    ].join(" ");
  };

  S.REGION_SLOTS = [
    "--series-1", "--series-2", "--series-3", "--series-4",
    "--series-5", "--series-6", "--series-7",
  ];

  // Colour follows the entity. The slot comes from the region's position in the
  // alphabetical list of ALL regions, so filtering never repaints a survivor —
  // callers must always pass the full list, never the filtered one.
  S.regionColorVar = function (region, allRegions) {
    const names = Array.from(new Set(allRegions)).sort();
    const index = names.indexOf(region);
    const slot = S.REGION_SLOTS[index < 0 ? 0 : index % S.REGION_SLOTS.length];
    return "var(" + slot + ")";
  };
})(globalThis.SOLAR);
