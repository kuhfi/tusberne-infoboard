"use strict";

// Nur geprüfte, ausdrücklich öffentliche Datensätze rendern. Keine HTML-Injektion aus Daten.
(function () {
  // Vier sichtbare Infoboard-Kacheln; ältere Export-Kategorien bleiben kompatibel.
  const tiles = [
    { id: "training", name: "Training", hint: "Trainingspläne, Trainingsinhalte und Lageplan Tore",
      icon: "🏃", sourceIds: ["trainingsplaene", "training"] },
    { id: "belegung", name: "Belegung", hint: "Kabinenbelegungen Heimspiele und Belegung Fußballraum",
      icon: "📅", sourceIds: ["kabinen", "lageplan", "belegung"] },
    { id: "tabellen-news", name: "Tabellen / News", hint: "Tabellen und Neuigkeiten",
      icon: "📊", sourceIds: ["fussball", "news", "tabellen-news"] },
    { id: "mannschaften-ansprechpartner", name: "Mannschaften / Ansprechpartner",
      hint: "Mannschaften und Abteilungsleitung",
      icon: "👥", sourceIds: ["mannschaften", "ansprechpartner", "mannschaften-ansprechpartner"] }
  ];
  const sourceToTile = new Map();
  tiles.forEach(function (tile) {
    tile.sourceIds.forEach(function (id) { sourceToTile.set(id, tile); });
  });
  const ui = {
    tileGrid: document.getElementById("kategorien"),
    documents: document.getElementById("dokumente"),
    reset: document.getElementById("filter-zurueck"),
    heading: document.getElementById("contents-title"),
    notice: document.getElementById("meldungen"),
    count: document.getElementById("gesamtzahl")
  };
  const state = { items: [], tile: "alle" };

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
  function el(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (typeof content === "string") node.textContent = content;
    return node;
  }
  function setNotice(message) {
    ui.notice.textContent = message;
    ui.notice.hidden = false;
  }
  function renderTiles() {
    ui.tileGrid.replaceChildren();
    tiles.forEach(function (tile) {
      const count = state.items.filter(function (item) { return item.tile === tile; }).length;
      const button = el("button", "category category--" + tile.id);
      button.type = "button";
      button.setAttribute("aria-pressed", String(state.tile === tile.id));
      button.setAttribute("aria-label", tile.name + " anzeigen");
      const top = el("span", "category-top");
      const icon = el("span", "category-icon", tile.icon);
      icon.setAttribute("aria-hidden", "true");
      top.append(icon);
      const bottom = el("span", "category-bottom");
      bottom.append(el("span", "category-count", count ? count + (count === 1 ? " Inhalt" : " Inhalte") : "Bereich öffnen"),
        el("span", "category-arrow", "↗"));
      button.append(top, el("span", "category-title", tile.name),
        el("span", "category-subtitle", tile.hint), bottom);
      button.addEventListener("click", function () {
        selectTile(state.tile === tile.id ? "alle" : tile.id);
      });
      ui.tileGrid.append(button);
    });
  }
  function selectTile(id) {
    state.tile = id;
    render();
    const target = document.getElementById(id === "alle" ? "themen" : "inhalte");
    target.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"
    });
  }
  function renderDocuments() {
    ui.documents.replaceChildren();
    const selectedTile = tiles.find(function (tile) { return tile.id === state.tile; });
    // Optionale Nummern legen die Reihenfolge innerhalb einer Kachel fest.
    // Ohne Nummer bleibt die Reihenfolge des öffentlichen Inhaltsverzeichnisses bestehen.
    const selected = state.items.filter(function (item) { return item.tile === selectedTile; })
      .sort(function (a, b) { return a.order - b.order; });
    ui.heading.textContent = selectedTile ? selectedTile.name : "Alle Inhalte";
    ui.reset.hidden = !selectedTile;
    ui.count.textContent = selected.length + (selected.length === 1 ? " Inhalt" : " Inhalte");

    if (selected.length === 0) {
      setNotice("Für die Kachel „" + selectedTile.name + "“ sind noch keine öffentlichen Inhalte freigegeben.");
      return;
    }
    ui.notice.hidden = true;
    selected.forEach(function (item) {
      // Training: ein direkter Link pro Inhalt, ohne zusätzlichen Aufklapp-Schritt.
      if (item.tile.id === "training") {
        const card = el("a", "document document-direct");
        card.href = item.url;
        card.target = "_blank";
        card.rel = "noopener noreferrer";
        const arrow = el("span", "doc-direct-arrow", "→");
        arrow.setAttribute("aria-hidden", "true");
        const content = el("span", "doc-direct-content");
        content.append(el("span", "doc-title", item.title));
        if (item.description) content.append(el("span", "doc-description", item.description));
        const stand = formattedDate(item.updated_at);
        if (stand) content.append(el("span", "doc-time", "Dateistand: " + stand));
        card.append(arrow, content);
        ui.documents.append(card);
        return;
      }
      const card = el("details", "document");
      const summary = el("summary", "");
      summary.append(el("span", "doc-title", item.title),
        el("span", "doc-category", item.tile.name));
      card.append(summary);
      const body = el("div", "document-body");
      if (item.description) body.append(el("p", "", item.description));
      const link = el("a", "doc-open",
        item.kind === "pdf" ? "PDF öffnen" : (item.kind === "image" ? "Bild öffnen" : "Ansehen"));
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
    renderTiles();
    const showingContents = state.tile !== "alle";
    document.getElementById("inhalte").hidden = !showingContents;
    if (showingContents) renderDocuments();
  }
  function initialize() {
    ui.reset.addEventListener("click", function () { selectTile("alle"); });
    render();
    fetch("./data/content.json", { cache: "no-store" })
      .then(function (response) {
        if (!response.ok) throw new Error("Datenabruf fehlgeschlagen");
        return response.json();
      })
      .then(function (data) {
        if (!data || data.schema_version !== 1 || !Array.isArray(data.items) ||
          (data.mode !== "preview" && data.mode !== "published")) {
          throw new Error("Unbekanntes Datenformat");
        }
        state.items = data.items.filter(function (item) {
          return item && item.public === true && sourceToTile.has(item.category)
            && typeof item.title === "string" && item.title.length > 0 && item.title.length <= 140
            && ["pdf", "image", "link"].includes(item.kind) && safeLink(item.url);
        }).map(function (item) {
          return { tile: sourceToTile.get(item.category), title: item.title, kind: item.kind,
            url: safeLink(item.url),
            description: typeof item.description === "string" ? item.description.slice(0, 500) : "",
            updated_at: item.updated_at,
            order: Number.isInteger(item.order) && item.order > 0 && item.order < 10000
              ? item.order : Number.MAX_SAFE_INTEGER };
        });
        render();
      })
      .catch(function () {
        if (location.protocol === "file:") {
          setNotice("Die Gestaltung ist sichtbar. Die JSON-Daten sind beim direkten Öffnen als Datei nicht abrufbar.");
        } else {
          setNotice("Der Datenabruf ist fehlgeschlagen. Bitte später erneut versuchen.");
        }
      });
  }
  initialize();
}());
