/* fakedom.mjs — the smallest document the dashboard actually needs. */

class ClassList {
  constructor() { this.items = new Set(); }
  add(...names) { names.forEach((n) => this.items.add(n)); }
  remove(...names) { names.forEach((n) => this.items.delete(n)); }
  contains(name) { return this.items.has(name); }
  toString() { return Array.from(this.items).join(" "); }
}

class Element {
  constructor(doc, tag, ns) {
    this.ownerDocument = doc;
    this.tagName = tag.toUpperCase();
    this.localName = tag;
    this.namespaceURI = ns || null;
    this.attributes = {};
    this.childNodes = [];
    this.parentNode = null;
    this.classList = new ClassList();
    this.dataset = {};
    this.style = {};
    this.listeners = {};
    this.hidden = false;
    this._text = "";
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name === "id") this.ownerDocument.index(this);
    if (name === "class") {
      this.classList = new ClassList();
      this.classList.add(...String(value).split(/\s+/).filter(Boolean));
    }
  }

  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attributes, name)
      ? this.attributes[name]
      : null;
  }

  appendChild(child) {
    child.parentNode = this;
    this.childNodes.push(child);
    return child;
  }

  append(...children) { children.forEach((c) => this.appendChild(c)); }

  replaceChildren(...children) {
    this.childNodes = [];
    this._text = "";
    children.forEach((c) => this.appendChild(c));
  }

  addEventListener(type, handler) {
    (this.listeners[type] = this.listeners[type] || []).push(handler);
  }

  dispatch(type, event) {
    for (const handler of this.listeners[type] || []) handler(event || { target: this });
  }

  set textContent(value) { this._text = String(value); this.childNodes = []; }

  get textContent() {
    return this._text + this.childNodes.map((c) => c.textContent).join("");
  }

  descendants() {
    return this.childNodes.flatMap((c) => [c, ...c.descendants()]);
  }

  matches(selector) {
    if (selector.startsWith("#")) return this.attributes.id === selector.slice(1);
    if (selector.startsWith(".")) return this.classList.contains(selector.slice(1));
    if (selector.startsWith("[")) {
      const [name, raw] = selector.slice(1, -1).split("=");
      if (raw === undefined) return this.getAttribute(name) !== null;
      return this.getAttribute(name) === raw.replace(/["']/g, "");
    }
    return this.localName === selector;
  }

  querySelectorAll(selector) {
    return this.descendants().filter((node) => node.matches(selector));
  }

  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

class FakeDocument {
  constructor() {
    this.byId = new Map();
    this.documentElement = new Element(this, "html");
    this.body = new Element(this, "body");
    this.documentElement.appendChild(this.body);
  }
  index(el) { this.byId.set(el.attributes.id, el); }
  createElement(tag) { return new Element(this, tag); }
  createElementNS(ns, tag) { return new Element(this, tag, ns); }
  getElementById(id) { return this.byId.get(id) || null; }
  querySelectorAll(selector) { return this.documentElement.querySelectorAll(selector); }
  querySelector(selector) { return this.documentElement.querySelector(selector); }
}

const CHROME_IDS = [
  "app", "kpis", "tabs", "filters", "region-chips", "risk-chips",
  "reset-filters", "toggle-tables", "filter-readout", "theme-toggle",
  "page-financial", "page-production", "page-sustainability",
  "caveats", "meta", "solar-data",
];

/** A document carrying the same ids as shell.html, plus the payload block. */
export function makeDocument(payload) {
  const doc = new FakeDocument();
  for (const id of CHROME_IDS) {
    const el = doc.createElement(id.startsWith("page-") ? "section" : "div");
    el.setAttribute("id", id);
    if (id.startsWith("page-") && id !== "page-financial") el.hidden = true;
    doc.body.appendChild(el);
  }
  doc.getElementById("solar-data").textContent = JSON.stringify(payload);
  for (const page of ["financial", "production", "sustainability"]) {
    const tab = doc.createElement("button");
    tab.setAttribute("id", "tab-" + page);
    tab.setAttribute("aria-controls", "page-" + page);
    tab.setAttribute("aria-selected", page === "financial" ? "true" : "false");
    doc.getElementById("tabs").appendChild(tab);
  }
  return doc;
}
