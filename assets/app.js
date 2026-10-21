"use strict";

// Ausschließlich explizit freigegebene Datensätze rendern. Nie HTML aus Fremddaten einsetzen.
(function () {
  const categories = [
    { id: "trainingsplaene", name: "Trainingspläne", hint: "Berne & Farmsen", icon: "📅" },
    { id: "kabinen", name: "Kabinenbelegung", hint: "Training & Spieltage", icon: "🚪" },
    { id: "fussball", name: "Spiele & Tabellen", hint: "Ergebnisse & Staffeln", icon: "⚽" },
    { id: "mannschaften", name: "Mannschaften", hint: "Teams & Informationen", icon: "👥" },
    { id: "news", name: "News & Termine", hint: "Aktuelles vom Verein", icon: "📣" },
    { id: "lageplan", name: "Platz & Lageplan", hint: "Tore & Orientierung", icon: "📍" }
  ];
  const allowed = new Map(categories.map(function (c) { return [c.id, c]; }));
  const ui = {
    categoryList: document.getElementById("kategorien"),
    documents: document.getElementById("dokumente"),
    search: document.getElementById("suche"),
    chips: document.getElementById("filter-chips"),
    notice: document.getElementById("meldungen"),
    status: document.getElementById("status-label"),
    stand: document.getElementById("datenstand"),
    count: document.getElementById("gesamtzahl")
  };
  const state = { items: [], category: "alle", search: "", mode: "preview" };

  function safeLink(value) {
    if (typeof value !== "string" || !value || value.length > 1800) return null;
    try {
      const url = new URL(value, document.baseURI);
      if (url.protocol !== "https:" && url.protocol !== "http:") return null;
      if (url.origin !== location.origin && url.protocol !== "https:") return null;
      if (url.username || url.password) return null;
      if (!value.startsWith("https://") && !value.startsWith("./files/")) return null;
      if (value.includes("..") || value.includes("\\") || /%2f|%5c|%2e/i.test(value)) return null;
      return url.href;
    } catch (_error) {
      return null;
    }
  }
  function formattedDate(value) {
    if (!value || typeof value !== "string") return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return new Intl.DateTimeFormat("de-DE", {
      dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Berlin"
    }).format(date);
  }
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (typeof text === "string") node.textContent = text;
    return node;
  }
  function setNotice(text) {
    ui.notice.textContent = text;
    ui.notice.hidden = false;
  }
  function renderCategories() {
    ui.categoryList.replaceChildren();
    categories.forEach(function (cat) {
      const count = state.items.filter(function (item) { return item.category === cat.id; }).length;
      const button = el("button", "category");
      button.type = "button";
      button.setAttribute("aria-pressed", String(state.category === cat.id));
      button.append(el("span", "category-title", cat.name));
      button.append(el("span", "category-subtitle", cat.hint + " · " + count + " Inhalte"));
      button.addEventListener("click", function () {
        setCategory(state.category === cat.id ? "alle" : cat.id);
      });
      ui.categoryList.append(button);
    });
  }
  function setCategory(id) {
    state.category = id;
    render();
    document.getElementById("inhalte").scrollIntoView({ behavior: "smooth" });
  }
  function renderChips() {
    ui.chips.replaceChildren();
    [{ id: "alle", name: "Alle" }].concat(categories).forEach(function (cat) {
      const button = el("button", "chip", cat.name);
      button.type = "button";
      button.setAttribute("aria-pressed", String(state.category === cat.id));
      button.addEventListener("click", function () { setCategory(cat.id); });
      ui.chips.append(button);
    });
  }
  function renderDocuments() {
    ui.documents.replaceChildren();
    const term = state.search.toLocaleLowerCase("de-DE");
    const selected = state.items.filter(function (item) {
      if (state.category !== "alle" && state.category !== item.category) return false;
      return (item.title + " " + (item.description || "") + " " + allowed.get(item.category).name)
        .toLocaleLowerCase("de-DE").includes(term);
    });
    if (selected.length === 0) {
      setNotice(state.items.length
        ? "Für diese Auswahl sind keine freigegebenen Inhalte vorhanden."
        : "Es wurden noch keine Inhalte für die Öffentlichkeit freigegeben. Die automatische Datenübernahme wird eingerichtet.");
      return;
    }
    ui.notice.hidden = true;
    selected.forEach(function (item) {
      const card = el("details", "document");
      const category = allowed.get(item.category);
      const summary = el("summary", "");
      const title = el("span", "doc-title", item.title);
      summary.append(title);
      summary.append(el("span", "doc-category", category.name));
      card.append(summary);
      const body = el("div", "document-body");
      if (item.description) body.append(el("p", "", item.description));
      const link = el("a", "doc-open", item.kind === "pdf" ? "PDF öffnen" : (item.kind === "image" ? "Bild öffnen" : "Ansehen"));
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      body.append(link);
      const stand = formattedDate(item.updated_at);
      if (stand) body.append(el("span", "doc-time", "Dateistand: " + stand));
      card.append(body);
      ui.documents.append(card);
    });
  }

  function render() {
    renderCategories();
    renderChips();
    renderDocuments();
    ui.count.textContent = state.items.length + " freigegebene Inhalte";
  }
  function initialize() {
    document.querySelectorAll("[data-go-category]").forEach(function (button) {
      button.addEventListener("click", function () {
        const id = button.getAttribute("data-go-category");
        if (allowed.has(id)) setCategory(id);
      });
    });
    ui.search.addEventListener("input", function () { state.search = ui.search.value.trim(); renderDocuments(); });
    render();

    fetch("./data/content.json", { cache: "no-store" })
      .then(function (response) { if (!response.ok) throw new Error("Datenabruf fehlgeschlagen"); return response.json(); })
      .then(function (data) {
        if (!data || data.schema_version !== 1 || !Array.isArray(data.items) || (data.mode !== "preview" && data.mode !== "published")) {
          throw new Error("Unbekanntes Datenformat");
        }
        state.mode = data.mode;
        state.items = data.items.filter(function (item) {
          return item && item.public === true && allowed.has(item.category)
            && typeof item.title === "string" && item.title.length > 0 && item.title.length <= 140
            && ["pdf","image","link"].includes(item.kind) && safeLink(item.url);
        }).map(function (item) {
          return { category: item.category, title: item.title, kind: item.kind,
            url: safeLink(item.url), description: typeof item.description === "string" ? item.description.slice(0, 500) : "",
            updated_at: item.updated_at };
        });
        const checked = formattedDate(data.generated_at);
        ui.stand.textContent = checked ? "Export erstellt: " + checked : "Noch kein bestätigter Datenstand";
        if (data.mode === "published" && state.items.length) {
          ui.status.textContent = "Öffentlich freigegebene Inhalte";
          document.querySelector(".dot").classList.add("is-live");
        } else {
          ui.status.textContent = "Vorschau · Veröffentlichung noch nicht freigegeben";
        }
        render();
      })
      .catch(function () {
        if (location.protocol === "file:") {
          ui.status.textContent = "Lokale Designvorschau · Daten werden erst über einen Webserver geladen";
          setNotice("Die Gestaltung ist sichtbar. Die JSON-Daten sind beim direkten Öffnen als Datei nicht abrufbar.");
        } else {
          ui.status.textContent = "Daten derzeit nicht verfügbar";
          setNotice("Der Datenabruf ist fehlgeschlagen. Bitte später erneut versuchen.");
        }
      });
  }
  initialize();
}());
