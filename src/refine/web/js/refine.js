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
        return p.flags[k] && window.rfKeep.indexOf(k) < 0 && /^(refine|rf-s-[\w-]+)$/.test(k);
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
      if (link && /^\d+$/.test(tr.id)) {
        // As in the design: a click selects the deck and stays on Home (the
        // headline's Study button follows it); a double-click opens Anki's
        // overview. With the "overview" setting, Anki's own handler runs.
        (function (id) {
          var pending = null;
          link.addEventListener("click", function (ev) {
            if (!document.documentElement.classList.contains("rf-click-select") || ev.shiftKey) return;
            ev.preventDefault();
            ev.stopImmediatePropagation(); // Anki's inline onclick would open the overview
            // selecting re-renders the page, so wait briefly for a double-click
            if (pending) clearTimeout(pending);
            pending = setTimeout(function () {
              pending = null;
              pycmd("refine:deck_browser:select:" + id);
            }, 250);
          }, true);
          link.addEventListener("dblclick", function (ev) {
            if (!document.documentElement.classList.contains("rf-click-select")) return;
            ev.preventDefault();
            if (pending) {
              clearTimeout(pending);
              pending = null;
            }
            pycmd("open:" + id);
          });
        })(tr.id);
        link.title = "Click to select · double-click for the overview";
      }
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

  // Ctrl+K focuses the header search (shell pages only; Anki doesn't use it here)
  document.addEventListener("keydown", function (ev) {
    if ((ev.ctrlKey || ev.metaKey) && !ev.altKey && !ev.shiftKey && (ev.key === "k" || ev.key === "K")) {
      var input = document.querySelector(".rf-search input");
      if (input) {
        ev.preventDefault();
        input.focus();
      }
    }
  });

  // Overview: Esc goes back to Home.
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && document.documentElement.classList.contains("rf-page-Overview")) {
      ev.preventDefault();
      pycmd("decks");
    }
  });

  function onReady() {
    if (document.documentElement.classList.contains("rf-page-DeckBrowser")) enhanceDeckRows();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", onReady);
  } else {
    onReady();
  }
})();
