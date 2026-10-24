/* Refine runtime for legacy Anki webviews. Loaded at the start of <body>. */
(function () {
  "use strict";
  if (window.rfApply) return;

  // Live settings: toggle Refine's html classes and swap the token stylesheet.
  window.rfApply = function (p) {
    var d = document.documentElement;
    // card webviews only ever carry the card-layer classes, never tokens
    var cardsOnly = d.dataset.rfScope === "cards";
    Object.keys(p.flags || {}).forEach(function (k) {
      if (cardsOnly && !/^rf-(cards|furigana)-/.test(k)) return;
      d.classList.toggle(k, !!p.flags[k]);
    });
    // pages that reset <html> classes keep a wanted-list (see overview.py)
    if (window.rfKeep) {
      window.rfKeep = window.rfKeep.filter(function (k) {
        return !(k in p.flags) || p.flags[k];
      }).concat(Object.keys(p.flags).filter(function (k) {
        return p.flags[k] && window.rfKeep.indexOf(k) < 0 && /^(refine|rf-s-overview)$/.test(k);
      }));
    }
    if (p.tokens && p.styleId && !cardsOnly) {
      var s = document.getElementById(p.styleId);
      if (!s) {
        s = document.createElement("style");
        s.id = p.styleId;
        document.head.appendChild(s);
      }
      s.textContent = p.tokens;
    }
  };

  window.rfSetState = function (state) {
    document.documentElement.dataset.rfState = state;
  };

  // Home panels: data arrives from a background query after render.
  window.rfFillHome = function (p) {
    Object.keys(p).forEach(function (key) {
      if (key === "pace") {
        var pace = document.getElementById("rf-pace");
        if (pace) pace.textContent = p.pace;
        return;
      }
      var el = document.querySelector('[data-rf-fill="' + key + '"]');
      if (el) el.innerHTML = p[key];
    });
  };

  // Deck list: annotate depth and add a per-row Study button. Anki's own
  // markup, handlers and drag-and-drop are left untouched.
  function enhanceDeckRows() {
    var rows = document.querySelectorAll("tr.deck");
    for (var i = 0; i < rows.length; i++) {
      var tr = rows[i];
      if (tr.dataset.rfDone) continue;
      tr.dataset.rfDone = "1";
      var td = tr.querySelector("td.decktd");
      var lead = td && td.firstChild && td.firstChild.nodeType === 3 ? td.firstChild.nodeValue : "";
      var nbsp = (lead.match(/ /g) || []).length;
      tr.dataset.rfDepth = String(Math.round(nbsp / 6));
      var due = tr.querySelector(".new-count, .learn-count, .review-count");
      if (due) tr.classList.add("rf-has-due");
      var link = tr.querySelector("a.deck");
      var name = link ? link.textContent.trim() : "";
      var opts = tr.querySelector("td.opts");
      if (opts && /^\d+$/.test(tr.id)) {
        var gear = opts.querySelector("a");
        if (gear) {
          gear.setAttribute("role", "button");
          gear.setAttribute("tabindex", "0");
          gear.setAttribute("aria-label", "Options for " + name);
          gear.title = "Options";
          gear.addEventListener("keydown", function (ev) {
            if (ev.key === "Enter" || ev.key === " ") {
              ev.preventDefault();
              this.click();
            }
          });
        }
        var b = document.createElement("button");
        b.className = "rf-row-study";
        b.type = "button";
        b.textContent = "Study";
        b.setAttribute("aria-label", "Study " + name);
        b.addEventListener("click", (function (id) {
          return function (ev) {
            ev.stopPropagation();
            pycmd("refine:deck_browser:study:" + id);
          };
        })(tr.id));
        opts.insertBefore(b, opts.firstChild);
      }
    }
  }

  function onReady() {
    if (document.documentElement.classList.contains("rf-page-DeckBrowser")) enhanceDeckRows();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", onReady);
  } else {
    onReady();
  }
})();
