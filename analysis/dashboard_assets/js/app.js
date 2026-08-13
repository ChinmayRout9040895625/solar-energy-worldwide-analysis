/* app.js — chrome, chart registry, and the single re-render path.
   Every state change goes through render(): one filter slice, one set of
   numbers, no chart holding a stale view. */
(function (S) {
  "use strict";

  S.buildContext = function (payload, state) {
    const cities = S.filterCities(payload.cities, state);
    return {
      payload: payload,
      state: state,
      cities: cities,
      regions: S.regionRollup(cities),
      countries: S.countryRollup(cities),
      totals: S.totalsOf(cities),
      allRegions: S.allRegionsOf(payload),
      allBands: S.BANDS,
    };
  };

  function kpiTile(value, label) {
    return S.el("div", { class: "kpi" }, [
      S.el("span", { class: "kpi-value", text: value }),
      S.el("span", { class: "kpi-label", text: label }),
    ]);
  }

  function renderKpis(doc, ctx) {
    const t = ctx.totals;
    S.clear(doc.getElementById("kpis")).append(
      kpiTile(S.fmtInt(t.cities), "Cities in view"),
      kpiTile(S.fmtInt(t.countries), "Countries"),
      kpiTile(S.fmt2(t.co2_tons), "Tonnes CO₂ avoided per year"),
      kpiTile(S.fmtCompact(t.installations), "Installations"),
      kpiTile(S.fmtCompact(t.production_kwh), "kWh produced per year")
    );
  }

  function chip(kind, value, selected, colorVar, onToggle) {
    const input = S.el("input", { type: "checkbox" });
    if (selected) input.setAttribute("checked", "checked");
    const key = colorVar
      ? S.el("span", { class: "chip-key", style: "background:" + colorVar })
      : null;
    const label = S.el("label", { class: "chip", "data-selected": String(selected) }, [
      input,
      S.el("span", { class: "chip-body" }, [
        S.el("span", { class: "chip-check", text: "✓" }),
        key,
        S.el("span", { text: value }),
      ]),
    ]);
    input.addEventListener("change", () => onToggle(kind, value));
    return label;
  }

  function renderChips(doc, ctx, onToggle) {
    const regionBox = S.clear(doc.getElementById("region-chips"));
    const regionChips = S.el("div", { class: "chips" });
    for (const region of ctx.allRegions) {
      regionChips.appendChild(
        chip(
          "regions",
          region,
          ctx.state.regions.indexOf(region) >= 0,
          S.regionColorVar(region, ctx.allRegions),
          onToggle
        )
      );
    }
    regionBox.appendChild(regionChips);

    const riskBox = S.clear(doc.getElementById("risk-chips"));
    const riskChips = S.el("div", { class: "chips" });
    for (const band of ctx.allBands) {
      riskChips.appendChild(
        chip("bands", band, ctx.state.bands.indexOf(band) >= 0, null, onToggle)
      );
    }
    riskBox.appendChild(riskChips);
  }

  function renderCharts(doc, ctx, showTables) {
    for (const page of S.PAGES) {
      const host = S.clear(doc.getElementById("page-" + page.id));
      for (const chart of S.charts.filter((c) => c.page === page.id)) {
        const plot = S.el("div", { class: "plot" });
        const card = S.el("figure", {
          class: "card" + (chart.wide ? " wide" : ""),
          "data-chart": chart.id,
        }, [
          S.el("figcaption", null, [
            S.el("h3", { text: chart.title }),
            S.el("p", { class: "definition", text: chart.definition }),
          ]),
          plot,
        ]);
        if (chart.render) chart.render(plot, ctx);
        if (chart.callout) {
          card.appendChild(S.el("p", { class: "callout", text: chart.callout(ctx) }));
        }
        if (chart.table) {
          const table = S.buildTable(chart.table(ctx));
          table.hidden = !showTables;
          card.appendChild(table);
        }
        host.appendChild(card);
      }
    }
  }

  function renderCaveats(doc, payload) {
    S.clear(doc.getElementById("caveats")).append(
      ...payload.caveats.map((text) => S.el("li", { text: text }))
    );
    doc.getElementById("meta").textContent =
      "Source: " + payload.meta.source +
      " · built " + payload.meta.generated_utc +
      " · spec " + payload.meta.spec;
  }

  function showPage(doc, pageId) {
    for (const page of S.PAGES) {
      const panel = doc.getElementById("page-" + page.id);
      const tab = doc.getElementById(page.tabId);
      const active = page.id === pageId;
      panel.hidden = !active;
      if (tab) tab.setAttribute("aria-selected", String(active));
    }
  }

  S.mount = function (document_) {
    const doc = S.useDocument(document_ || globalThis.document);
    const payload = S.readPayload(doc);
    let state = S.initialState(payload);
    let showTables = false;

    function onToggle(kind, value) {
      const all = kind === "regions" ? S.allRegionsOf(payload) : S.BANDS;
      setState(Object.assign({}, state, { [kind]: S.toggleValue(state[kind], value, all) }));
    }

    function render() {
      const ctx = S.buildContext(payload, state);
      ctx.isolate = (kind, value) => {
        const all = kind === "regions" ? S.allRegionsOf(payload) : S.BANDS;
        setState(Object.assign({}, state, {
          [kind]: S.isolateValue(state[kind], value, all),
        }));
      };
      renderKpis(doc, ctx);
      renderChips(doc, ctx, onToggle);
      renderCharts(doc, ctx, showTables);
      doc.getElementById("filter-readout").textContent = S.describeFilter(
        payload.cities, ctx.cities, state, ctx.allRegions, ctx.allBands
      );
      showPage(doc, state.page);
      return ctx;
    }

    function setState(next) { state = next; return render(); }

    const reset = doc.getElementById("reset-filters");
    if (reset) {
      reset.addEventListener("click", () =>
        setState(Object.assign({}, S.initialState(payload), { page: state.page }))
      );
    }

    const tables = doc.getElementById("toggle-tables");
    if (tables) {
      tables.addEventListener("change", () => { showTables = !showTables; render(); });
    }

    for (const page of S.PAGES) {
      const tab = doc.getElementById(page.tabId);
      if (tab) {
        tab.addEventListener("click", () =>
          setState(Object.assign({}, state, { page: page.id }))
        );
      }
    }

    const themeToggle = doc.getElementById("theme-toggle");
    if (themeToggle) {
      themeToggle.addEventListener("click", () => {
        const root = doc.documentElement;
        const dark = root.getAttribute("data-theme") === "dark";
        root.setAttribute("data-theme", dark ? "light" : "dark");
        themeToggle.setAttribute("aria-pressed", String(!dark));
        themeToggle.textContent = dark ? "Dark theme" : "Light theme";
      });
    }

    renderCaveats(doc, payload);
    const ctx = render();
    return { getState: () => state, setState: setState, ctx: ctx };
  };

  if (typeof globalThis.document !== "undefined" && globalThis.document.getElementById) {
    if (globalThis.document.getElementById("solar-data")) S.mount(globalThis.document);
  }
})(globalThis.SOLAR);
